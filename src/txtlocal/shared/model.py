from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel

from txtlocal.shared.table import Table, plain, sort_ts

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef

Rfc3339 = Annotated[datetime, PlainSerializer(sort_ts, return_type=str, when_used="json")]


class Model(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        frozen=True,
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )


def model_of[M: Model](kind: type[M], item: Mapping[str, AttributeValueTypeDef]) -> M:
    return kind.model_validate({name: plain(value) for name, value in item.items()})


async def get_model[M: Model](
    table: Table, kind: type[M], item_key: dict[str, AttributeValueTypeDef]
) -> M | None:
    response = await table.client.get_item(Key=item_key, TableName=table.name)
    item = response.get("Item")
    return model_of(kind, item) if item else None
