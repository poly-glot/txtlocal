from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SesEmail:
    send_email: Callable[..., Awaitable[object]]
    sender: str

    async def send(self, to: str, subject: str, body: str) -> None:
        await self.send_email(
            Destination={"ToAddresses": [to]},
            Message={
                "Body": {"Text": {"Charset": "UTF-8", "Data": body}},
                "Subject": {"Charset": "UTF-8", "Data": subject},
            },
            Source=self.sender,
        )
