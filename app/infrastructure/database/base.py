from enum import Enum as PyEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def pg_enum[E: PyEnum](enum_cls: type[E], *, name: str) -> SAEnum:
    """Postgres ENUM column mapped by member *value*, not member name.

    SQLAlchemy's Enum type serializes by `.name` by default. Our StrEnum
    members use upper-case names with lower-case values (`ACTIVE = "active"`),
    so without this the column would try to read/write "ACTIVE" against a
    database that actually stores "active".
    """
    return SAEnum(enum_cls, name=name, values_callable=lambda cls: [member.value for member in cls])
