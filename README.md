# ESG Heading Restoration

[中文说明](#中文说明) | [English](#overview)

## 中文说明

这是一个用于恢复 ESG 报告及其他长文档标题层级的 Python 工具包。它先清理由 OCR 或文档转换产生的 Markdown 噪声，再根据目录 JSON 或目录图片恢复标题。仓库仅包含源代码、测试和合成示例；不包含任何企业报告、PDF、转换结果或 API 凭据。

## Overview

ESG Heading Restoration is a Python toolkit for restoring the heading hierarchy of Markdown documents. It supports an offline workflow using an existing table-of-contents (ToC) JSON file and an optional vision-LLM workflow that extracts the ToC from an image.

The alignment pipeline uses three ordered stages:

1. Exact and normalized heading matching.
2. BM25 and fuzzy matching for headings that differ slightly.
3. Deterministic fallback or optional LLM-guided insertion for unresolved headings.

## Installation

Requires Python 3.10 or later.

```bash
git clone https://github.com/<your-account>/esg-heading-restoration.git
cd esg-heading-restoration
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For enhanced Simplified/Traditional Chinese conversion, install the optional extras:

```bash
python -m pip install -e ".[chinese,dev]"
```

## Quick start

The included synthetic example runs fully offline:

```bash
esg-heading-restore \
  --markdown-input examples/input.md \
  --toc-json examples/titles.json \
  --cleaned-output examples/input.cleaned.md \
  --aligned-output examples/input.aligned.md
```

The two generated files are ignored by Git. Review `examples/input.aligned.md` to inspect the restored hierarchy.

You can also invoke the module directly:

```bash
python -m emnlp_submission.main --help
```

## Input modes

### Existing ToC JSON (offline)

Provide a JSON array whose nodes have a `title` and optional `subtitles` list:

```json
[
  {
    "title": "Environmental Responsibility",
    "subtitles": ["Carbon Emissions"]
  }
]
```

```bash
esg-heading-restore \
  --markdown-input report.md \
  --toc-json titles.json \
  --cleaned-output report.cleaned.md \
  --aligned-output report.aligned.md
```

### ToC image (optional network access)

When only a ToC image is available, configure a compatible chat-completions endpoint at runtime. The API key is never stored in the repository.

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.example.com/v1"
export LLM_MODEL="your-vision-model"

esg-heading-restore \
  --markdown-input report.md \
  --toc-image toc.jpg \
  --cleaned-output report.cleaned.md \
  --aligned-output report.aligned.md \
  --extracted-toc-output titles.json
```

`--toc-image` sends the image to the endpoint configured by `LLM_BASE_URL`. If unresolved headings remain and both `LLM_API_KEY` and `LLM_BASE_URL` are set, the relevant Markdown context can also be sent to that endpoint. Review your data-handling obligations before enabling either network path.

Configuration variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `LLM_API_KEY` | API credential for the compatible endpoint | none |
| `LLM_BASE_URL` | Endpoint root; `/chat/completions` is appended | none |
| `LLM_MODEL` | Model name | `Qwen3.5-27B` |
| `LLM_TIMEOUT` | Request timeout in seconds | `120` |
| `LLM_MAX_RETRIES` | Retry count for oversized images | `3` |

## Development

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

The GitHub Actions workflow runs these tests on supported Python versions for each push and pull request.

## Repository layout

```text
src/emnlp_submission/  Core package and command-line entry point
tests/                 Unit tests
examples/              Synthetic, non-sensitive example inputs
.github/               Continuous-integration and issue templates
```

## Data and security

This is a source-code-only release. See [DATA_POLICY.md](DATA_POLICY.md) for publication boundaries and [SECURITY.md](SECURITY.md) for reporting guidance.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Released under the [MIT License](LICENSE).
