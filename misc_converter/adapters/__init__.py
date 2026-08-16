"""어댑터 레지스트리 — 이름 → 어댑터 클래스."""

from __future__ import annotations

from misc_converter.adapters.aptiv import AptivAdapter
from misc_converter.adapters.base import Adapter
from misc_converter.adapters.csv_extractor import CsvExtractorAdapter
from misc_converter.adapters.djlp import DjlpAdapter
from misc_converter.adapters.pcap2pcd import Pcap2PcdAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    AptivAdapter.name: AptivAdapter,
    DjlpAdapter.name: DjlpAdapter,
    CsvExtractorAdapter.name: CsvExtractorAdapter,
    Pcap2PcdAdapter.name: Pcap2PcdAdapter,
}

__all__ = ["ADAPTERS", "Adapter", "AptivAdapter", "DjlpAdapter", "CsvExtractorAdapter", "Pcap2PcdAdapter"]
