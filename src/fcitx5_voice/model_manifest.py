"""Immutable upstream model manifests shared by setup and diagnostics."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DownloadFile:
    name: str
    sha256: str


@dataclass(frozen=True)
class ModelManifest:
    directory: str
    repository: str
    revision: str
    files: tuple[DownloadFile, ...]


STREAMING_MODEL = ModelManifest(
    directory='streaming-zipformer-bilingual-zh-en-2023-02-20',
    repository='csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20',
    revision='98590b7ed6443e77b714204da2757d75e1a642f4',
    files=(
        DownloadFile('encoder-epoch-99-avg-1.int8.onnx',
                     '8fa764187a261844f859d7143ebaa563af5d10adfece4c18a8f414c88cba2a9b'),
        DownloadFile('decoder-epoch-99-avg-1.onnx',
                     '2e3b5ec371f8899ee6acd829fd753ba45772df57a91bdf37cde3136354e7db7d'),
        DownloadFile('joiner-epoch-99-avg-1.int8.onnx',
                     '1ed689c5ed19dbaa725d9d191bb4822b5f4855a39e1ffd28cbc1f340d25b2ee0'),
        DownloadFile('tokens.txt',
                     'a8e0e4ec53810e433789b54a5c0134a7eaa2ffca595a6334d54c00da858841d3'),
    ),
)


OFFLINE_MODEL = ModelManifest(
    directory='sensevoice',
    repository='csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17',
    revision='2365baeacb507f821a0c8120fcee3d484dba7a07',
    files=(
        DownloadFile('model.int8.onnx',
                     'c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51'),
        DownloadFile('tokens.txt',
                     'f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc'),
    ),
)


MODELS = {'streaming': STREAMING_MODEL, 'offline': OFFLINE_MODEL}
