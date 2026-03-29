"""
Unified email parser supporting EML, MBOX, PST, OST, and MSG formats.
Each format has its own parser class that yields ParsedEmail objects.
"""
from __future__ import annotations

import email
import email.policy
import email.utils
import hashlib
import logging
import mailbox
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from email.header import decode_header
from pathlib import Path
from typing import Generator

import chardet

from app.models import ParsedAttachment, ParsedEmail

logger = logging.getLogger(__name__)


def _decode_str(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        detected = chardet.detect(value)
        enc = detected.get("encoding") or "utf-8"
        try:
            return value.decode(enc, errors="replace")
        except (UnicodeDecodeError, LookupError):
            return value.decode("utf-8", errors="replace")
    return str(value)


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            charset = charset or "utf-8"
            try:
                decoded.append(part.decode(charset, errors="replace"))
            except (UnicodeDecodeError, LookupError):
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(date_str)
    except Exception:
        try:
            parsed = email.utils.parsedate_to_datetime(date_str)
            return parsed
        except Exception:
            return None


def _extract_name_and_addr(addr_str: str | None) -> tuple[str, str]:
    if not addr_str:
        return "", ""
    decoded = _decode_header_value(addr_str)
    name, addr = email.utils.parseaddr(decoded)
    return name, addr


def _format_addr_list(addr_str: str | None) -> str:
    if not addr_str:
        return ""
    decoded = _decode_header_value(addr_str)
    addrs = email.utils.getaddresses([decoded])
    parts = []
    for name, addr in addrs:
        if name and addr:
            parts.append(f"{name} <{addr}>")
        elif addr:
            parts.append(addr)
        elif name:
            parts.append(name)
    return ", ".join(parts)


def _parse_mime_message(msg: email.message.Message, source: str = "", raw_bytes: bytes = b"") -> ParsedEmail:
    """Parse a standard email.message.Message into a ParsedEmail."""
    sender_name, sender_addr = _extract_name_and_addr(msg.get("From"))
    subject = _decode_header_value(msg.get("Subject"))
    recipients = _format_addr_list(msg.get("To"))
    cc = _format_addr_list(msg.get("Cc"))
    bcc = _format_addr_list(msg.get("Bcc"))
    message_id = msg.get("Message-ID", "")
    date = _parse_date(msg.get("Date"))

    # Capture all raw headers for forensic analysis
    raw_headers = ""
    try:
        raw_headers = "\n".join(f"{k}: {v}" for k, v in msg.items())
    except Exception:
        pass

    # Compute content hash (SHA-256 of raw bytes)
    content_hash = ""
    if raw_bytes:
        content_hash = hashlib.sha256(raw_bytes).hexdigest()

    body_text = ""
    body_html = ""
    attachments: list[ParsedAttachment] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition.lower() or (
                content_type not in ("text/plain", "text/html", "multipart/mixed",
                                     "multipart/alternative", "multipart/related")
            ):
                payload = part.get_payload(decode=True)
                if payload:
                    filename = part.get_filename()
                    if filename:
                        filename = _decode_header_value(filename)
                    else:
                        ext = content_type.split("/")[-1] if "/" in content_type else "bin"
                        filename = f"attachment.{ext}"
                    attachments.append(ParsedAttachment(
                        filename=filename,
                        content_type=content_type,
                        size=len(payload),
                        data=payload,
                    ))
            elif content_type == "text/plain" and not body_text:
                payload = part.get_payload(decode=True)
                if payload:
                    body_text = _decode_str(payload)
            elif content_type == "text/html" and not body_html:
                payload = part.get_payload(decode=True)
                if payload:
                    body_html = _decode_str(payload)
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            if content_type == "text/html":
                body_html = _decode_str(payload)
            else:
                body_text = _decode_str(payload)

    if not message_id:
        hash_data = f"{subject}{sender_addr}{date}{body_text[:200]}".encode()
        message_id = f"<generated-{hashlib.sha256(hash_data).hexdigest()[:16]}>"

    return ParsedEmail(
        message_id=message_id,
        subject=subject,
        sender=sender_addr,
        sender_name=sender_name,
        recipients=recipients,
        cc=cc,
        bcc=bcc,
        date=date,
        body_text=body_text,
        body_html=body_html,
        attachments=attachments,
        raw_headers=raw_headers,
        content_hash=content_hash,
    )


def parse_eml(file_path: str) -> Generator[ParsedEmail, None, None]:
    """Parse a single .eml file."""
    with open(file_path, "rb") as f:
        raw = f.read()
        msg = email.message_from_bytes(raw, policy=email.policy.default)
    yield _parse_mime_message(msg, source=os.path.basename(file_path), raw_bytes=raw)


def parse_eml_bytes(data: bytes, source: str = "") -> ParsedEmail:
    """Parse EML data from bytes."""
    msg = email.message_from_bytes(data, policy=email.policy.default)
    return _parse_mime_message(msg, source=source, raw_bytes=data)


def parse_mbox(file_path: str) -> Generator[ParsedEmail, None, None]:
    """Parse an .mbox file by streaming, yielding one ParsedEmail per message.
    Uses a line-by-line reader instead of mailbox.mbox to avoid a full-file
    TOC scan that blocks on multi-GB files.
    """
    file_size = os.path.getsize(file_path)
    source = os.path.basename(file_path)
    logger.info(f"Streaming mbox: {source} ({file_size / (1024*1024):.0f} MB)")

    count = 0
    current_lines: list[bytes] = []

    def _flush() -> ParsedEmail | None:
        if not current_lines:
            return None
        raw = b"".join(current_lines)
        try:
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            return _parse_mime_message(msg, source=source, raw_bytes=raw)
        except Exception as e:
            logger.warning(f"Failed to parse mbox message near #{count}: {e}")
            return None

    with open(file_path, "rb") as f:
        for line in f:
            if line.startswith(b"From ") and current_lines:
                parsed = _flush()
                if parsed is not None:
                    count += 1
                    yield parsed
                current_lines = []
            current_lines.append(line)

    # Flush the last message
    parsed = _flush()
    if parsed is not None:
        count += 1
        yield parsed

    logger.info(f"Mbox streaming complete: {source} — {count} messages yielded")


def parse_msg(file_path: str) -> Generator[ParsedEmail, None, None]:
    """Parse a .msg (Outlook) file using extract-msg."""
    try:
        import extract_msg
    except ImportError:
        logger.error("extract-msg not installed, cannot parse .msg files")
        return

    msg = extract_msg.Message(file_path)
    try:
        attachments = []
        for att in msg.attachments:
            try:
                data = att.data
                if data:
                    attachments.append(ParsedAttachment(
                        filename=att.longFilename or att.shortFilename or "attachment",
                        content_type=att.mimetype or "application/octet-stream",
                        size=len(data),
                        data=data,
                    ))
            except Exception as e:
                logger.warning(f"Failed to extract attachment from MSG: {e}")

        date = None
        if msg.date:
            date = _parse_date(str(msg.date))

        sender_name = msg.senderName or ""
        sender = msg.sender or ""
        if not sender and msg.senderName:
            sender = msg.senderName

        # Extract transport headers for forensic analysis
        raw_headers = ""
        try:
            header = msg.header
            if header:
                if isinstance(header, bytes):
                    raw_headers = header.decode("utf-8", errors="replace")
                else:
                    raw_headers = str(header)
        except Exception:
            pass

        # Compute content hash
        content_hash = ""
        try:
            with open(file_path, "rb") as fh:
                content_hash = hashlib.sha256(fh.read()).hexdigest()
        except Exception:
            pass

        yield ParsedEmail(
            message_id=msg.messageId or f"<msg-{hashlib.sha256(file_path.encode()).hexdigest()[:16]}>",
            subject=msg.subject or "",
            sender=sender,
            sender_name=sender_name,
            recipients=msg.to or "",
            cc=msg.cc or "",
            bcc=msg.bcc or "",
            date=date,
            body_text=msg.body or "",
            body_html=msg.htmlBody.decode("utf-8", errors="replace") if msg.htmlBody else "",
            attachments=attachments,
            raw_headers=raw_headers,
            content_hash=content_hash,
        )
    finally:
        msg.close()


def parse_pst(file_path: str) -> Generator[ParsedEmail, None, None]:
    """
    Parse a .pst or .ost file using readpst CLI tool (from pst-utils).
    Converts to mbox format first, then parses the resulting mbox files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = subprocess.run(
                ["readpst", "-b", "-o", tmpdir, "-r", file_path],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                logger.error(f"readpst failed: {result.stderr}")
                return
        except FileNotFoundError:
            logger.error("readpst not found — pst-utils not installed")
            return
        except subprocess.TimeoutExpired:
            logger.error("readpst timed out processing file")
            return

        # readpst outputs mbox files in the temp directory
        for root, _dirs, files in os.walk(tmpdir):
            for fname in files:
                fpath = os.path.join(root, fname)
                if os.path.getsize(fpath) == 0:
                    continue
                # Try to parse each output file as mbox
                try:
                    yield from parse_mbox(fpath)
                except Exception as e:
                    # May be a non-mbox file, try as eml
                    try:
                        yield from parse_eml(fpath)
                    except Exception:
                        logger.warning(f"Could not parse readpst output file {fname}: {e}")


# PST and OST use the same parser
parse_ost = parse_pst


def parse_olm(file_path: str) -> Generator[ParsedEmail, None, None]:
    """
    Parse a .olm (Outlook for Mac) file.
    OLM is a ZIP archive containing XML email files in paths like:
    com.microsoft.__Messages/<folder>/.../*.xml
    """
    import zipfile
    import xml.etree.ElementTree as ET

    source = os.path.basename(file_path)
    logger.info(f"Parsing OLM: {source}")
    count = 0

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".xml"):
                    continue
                # OLM stores emails in message directories
                if "Messages" not in name and "message" not in name.lower():
                    continue

                try:
                    data = zf.read(name)
                    root = ET.fromstring(data)

                    # OLM XML elements
                    subject = root.findtext(".//OPFMessageCopySubject", default="")
                    sender = root.findtext(".//OPFMessageCopySenderAddress", default="")
                    sender_name = root.findtext(".//OPFMessageCopySenderName", default="")
                    to = root.findtext(".//OPFMessageCopyToAddresses", default="")
                    cc = root.findtext(".//OPFMessageCopyCCAddresses", default="")
                    bcc = root.findtext(".//OPFMessageCopyBCCAddresses", default="")
                    date_str = root.findtext(".//OPFMessageCopySentTime", default="")
                    body_html = root.findtext(".//OPFMessageCopyHTMLBody", default="")
                    body_text = root.findtext(".//OPFMessageCopyBody", default="")
                    msg_id = root.findtext(".//OPFMessageCopyMessageID", default="")

                    date = _parse_date(date_str) if date_str else None

                    if not msg_id:
                        hash_data = f"{subject}{sender}{date_str}{body_text[:200]}".encode()
                        msg_id = f"<olm-{hashlib.sha256(hash_data).hexdigest()[:16]}>"

                    content_hash = hashlib.sha256(data).hexdigest()

                    # Extract attachments from OLM
                    attachments: list[ParsedAttachment] = []
                    for att_elem in root.findall(".//messageAttachment"):
                        att_name = att_elem.findtext("OPFAttachmentName", default="attachment")
                        att_mime = att_elem.findtext("OPFAttachmentContentType", default="application/octet-stream")
                        att_url = att_elem.findtext("OPFAttachmentURL", default="")
                        if att_url and att_url in zf.namelist():
                            try:
                                att_data = zf.read(att_url)
                                attachments.append(ParsedAttachment(
                                    filename=att_name,
                                    content_type=att_mime,
                                    size=len(att_data),
                                    data=att_data,
                                ))
                            except Exception:
                                pass

                    count += 1
                    yield ParsedEmail(
                        message_id=msg_id,
                        subject=subject,
                        sender=sender,
                        sender_name=sender_name,
                        recipients=to,
                        cc=cc,
                        bcc=bcc,
                        date=date,
                        body_text=body_text,
                        body_html=body_html,
                        attachments=attachments,
                        raw_headers="",
                        content_hash=content_hash,
                    )
                except ET.ParseError as e:
                    logger.warning(f"Failed to parse OLM XML {name}: {e}")
                except Exception as e:
                    logger.warning(f"Error parsing OLM entry {name}: {e}")
    except zipfile.BadZipFile:
        logger.error(f"Invalid OLM file (not a valid ZIP): {file_path}")
        return

    logger.info(f"OLM parsing complete: {source} — {count} messages")


def parse_edb(file_path: str) -> Generator[ParsedEmail, None, None]:
    """
    Parse a .edb (Exchange Database) file using esedbexport.
    Exports tables to a temp directory and attempts to parse email data
    from the exported content.
    """
    source = os.path.basename(file_path)
    logger.info(f"Parsing EDB: {source}")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = subprocess.run(
                ["esedbexport", "-t", os.path.join(tmpdir, "export"), file_path],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                logger.error(f"esedbexport failed: {result.stderr}")
                return
        except FileNotFoundError:
            logger.error("esedbexport not found — libesedb-utils not installed")
            return
        except subprocess.TimeoutExpired:
            logger.error("esedbexport timed out processing file")
            return

        # Walk the exported directory looking for parseable files
        count = 0
        for root, _dirs, files in os.walk(tmpdir):
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                if os.path.getsize(fpath) == 0:
                    continue

                # Try parsing as EML first, then as mbox
                try:
                    for parsed in parse_eml(fpath):
                        count += 1
                        yield parsed
                    continue
                except Exception:
                    pass

                try:
                    for parsed in parse_mbox(fpath):
                        count += 1
                        yield parsed
                except Exception:
                    pass

        logger.info(f"EDB parsing complete: {source} — {count} messages")


# Format dispatcher
PARSERS = {
    "eml": parse_eml,
    "mbox": parse_mbox,
    "msg": parse_msg,
    "pst": parse_pst,
    "ost": parse_ost,
    "olm": parse_olm,
    "edb": parse_edb,
}


def parse_email_file(file_path: str, format_hint: str | None = None) -> Generator[ParsedEmail, None, None]:
    """
    Parse an email file of any supported format.
    Auto-detects format from extension if format_hint is not provided.
    """
    if not format_hint:
        ext = Path(file_path).suffix.lower()
        from app.config import SUPPORTED_FORMATS
        format_hint = SUPPORTED_FORMATS.get(ext)

    if not format_hint or format_hint not in PARSERS:
        raise ValueError(f"Unsupported email format: {format_hint or Path(file_path).suffix}")

    parser = PARSERS[format_hint]
    yield from parser(file_path)
