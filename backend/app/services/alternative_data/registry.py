"""Registry for supported alternative-data adapters."""

from __future__ import annotations

from app.models import AlternativeSourceType
from app.services.alternative_data.base import AlternativeDataAdapter, SOURCE_DESCRIPTIONS
from app.services.alternative_data.ecommerce import EcommerceAdapter
from app.services.alternative_data.gst import GstAdapter
from app.services.alternative_data.mobility import MobilityAdapter
from app.services.alternative_data.telecom import TelecomAdapter
from app.services.alternative_data.upi import UpiAdapter
from app.services.alternative_data.utilities import UtilitiesAdapter


ADAPTERS: dict[AlternativeSourceType, AlternativeDataAdapter] = {
    AlternativeSourceType.GST: GstAdapter(),
    AlternativeSourceType.UPI: UpiAdapter(),
    AlternativeSourceType.TELECOM: TelecomAdapter(),
    AlternativeSourceType.UTILITIES: UtilitiesAdapter(),
    AlternativeSourceType.ECOMMERCE: EcommerceAdapter(),
    AlternativeSourceType.MOBILITY: MobilityAdapter(),
}


def supported_sources() -> list[dict[str, object]]:
    return [
        {
            "source_type": source.value,
            **SOURCE_DESCRIPTIONS[source],
            "mock_available": True,
        }
        for source in AlternativeSourceType
    ]


def get_adapter(source_type: AlternativeSourceType | str) -> AlternativeDataAdapter:
    source = AlternativeSourceType(source_type)
    return ADAPTERS[source]
