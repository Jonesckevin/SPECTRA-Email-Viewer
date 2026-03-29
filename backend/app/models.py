from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ParsedAttachment:
    filename: str
    content_type: str
    size: int
    data: bytes


@dataclass
class ParsedEmail:
    message_id: str = ""
    subject: str = ""
    sender: str = ""
    sender_name: str = ""
    recipients: str = ""
    cc: str = ""
    bcc: str = ""
    date: Optional[datetime] = None
    body_text: str = ""
    body_html: str = ""
    attachments: list[ParsedAttachment] = field(default_factory=list)
    raw_headers: str = ""
    content_hash: str = ""

    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0


@dataclass
class EmailRecord:
    id: int
    file_source: str
    message_id: str
    subject: str
    sender: str
    sender_name: str
    recipients: str
    cc: str
    bcc: str
    date: Optional[str]
    date_unix: Optional[float]
    body_text: str
    body_html: str
    has_attachments: bool
    is_starred: bool
    imported_at: str
    raw_headers: str = ""
    content_hash: str = ""

    @classmethod
    def from_row(cls, row: dict) -> EmailRecord:
        return cls(
            id=row["id"],
            file_source=row["file_source"],
            message_id=row["message_id"] or "",
            subject=row["subject"] or "",
            sender=row["sender"] or "",
            sender_name=row["sender_name"] or "",
            recipients=row["recipients"] or "",
            cc=row["cc"] or "",
            bcc=row["bcc"] or "",
            date=row["date"],
            date_unix=row["date_unix"],
            body_text=row["body_text"] or "",
            body_html=row["body_html"] or "",
            has_attachments=bool(row["has_attachments"]),
            is_starred=bool(row["is_starred"]),
            imported_at=row["imported_at"] or "",
            raw_headers=row.get("raw_headers") or "",
            content_hash=row.get("content_hash") or "",
        )

    def to_dict(self, include_body: bool = False) -> dict:
        d = {
            "id": self.id,
            "file_source": self.file_source,
            "message_id": self.message_id,
            "subject": self.subject,
            "sender": self.sender,
            "sender_name": self.sender_name,
            "recipients": self.recipients,
            "cc": self.cc,
            "bcc": self.bcc,
            "date": self.date,
            "has_attachments": self.has_attachments,
            "is_starred": self.is_starred,
            "imported_at": self.imported_at,
        }
        if include_body:
            d["body_text"] = self.body_text
            d["body_html"] = self.body_html
        return d
