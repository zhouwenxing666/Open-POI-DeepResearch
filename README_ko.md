<p align="center">
  <img src="assets/logo.jpg" width="200"/>
</p>

[English](README.md) | [中文](README_zh.md) | 한국어 | [日本語](README_ja.md)

# Open-POI-Deepresearch 프로젝트 개요

Open-POI-Deepresearch 프로젝트는 전면적인 여행 계획 보조 도구로, 개인에게 다양한 여행 서비스를 제공합니다. 예를 들어 주변의 xx를 찾거나, 여행 계획을 지정하는 등의 기능을 지원하며, 한 번의 클릭으로 고드(高德) 내비게이션/택시 링크를 생성할 수 있습니다. 이 프로젝트는 고드 mcp에서 제공하는 여행 도구 서비스를 기반으로 하고 있으며, 심층 검색과 자체 검증 기능을 지원합니다. 불확실한 정보에 대해서는 askhuman 도구를 통해 사용자에게 추가 질문을 하게 됩니다. 또한 최종 버전에서는 스트리밍 기능을 지원할 예정이며(현재 개발 중), 이 프로젝트가 사용자 각자가 소유한 여행 계획 보조 도구를 구축하는 데 도움이 되기를 바랍니다.

Open-POI-Deepresearch 프로젝트는 OpenManus 프로젝트를 기반으로 개발되었으며, 실행 환경은 OpenManus와 동일합니다. 사용자는 아래의 OpenManus 프로젝트 소개에서 해당 환경을 설치한 후, Open-POI-Deepresearch에서 제공하는 server_web.py를 사용하여 서비스를 시작하면 됩니다(명령어: python server_web.py).

# 👋 OpenManus

Manus는 놀라운 도구지만, OpenManus는 *초대 코드* 없이도 모든 아이디어를 실현할 수 있습니다! 🛫

우리 팀의 멤버인 [@Xinbin Liang](https://github.com/mannaandpoem)와 [@Jinyu Xiang](https://github.com/XiangJinyu) (핵심 작성자), 그리고 [@Zhaoyang Yu](https://github.com/MoshiQAQ), [@Jiayi Zhang](https://github.com/didiforgithub), [@Sirui Hong](https://github.com/stellaHSR)이 함께 했습니다. 우리는 [@MetaGPT](https://github.com/geekan/MetaGPT)로부터 왔습니다. 프로토타입은 단 3시간 만에 출시되었으며, 계속해서 발전하고 있습니다!

이 프로젝트는 간단한 구현에서 시작되었으며, 여러분의 제안, 기여 및 피드백을 환영합니다!

OpenManus를 통해 여러분만의 에이전트를 즐겨보세요!

또한 [OpenManus-RL](https://github.com/OpenManus/OpenManus-RL)을 소개하게 되어 기쁩니다. OpenManus와 UIUC 연구자들이 공동 개발한 이 오픈소스 프로젝트는 LLM 에이전트에 대해 강화 학습(RL) 기반 (예: GRPO) 튜닝 방법을 제공합니다.

## 프로젝트 데모

<video src="https://private-user-images.githubusercontent.com/61239030/420168772-6dcfd0d2-9142-45d9-b74e-d10aa75073c6.mp4?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NDEzMTgwNTksIm5iZiI6MTc0MTMxNzc1OSwicGF0aCI6Ii82MTIzOTAzMC80MjAxNjg3NzItNmRjZmQwZDItOTE0Mi00NWQ5LWI3NGUtZDEwYWE3NTA3M2M2Lm1wND9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNTAzMDclMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjUwMzA3VDAzMjIzOVomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTdiZjFkNjlmYWNjMmEzOTliM2Y3M2VlYjgyNDRlZDJmOWE3NWZhZjE1MzhiZWY4YmQ3NjdkNTYwYTU5ZDA2MzYmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.UuHQCgWYkh0OQq9qsUWqGsUbhG3i9jcZDAMeHjLt5T4" data-canonical-src="https://private-user-images.githubusercontent.com/61239030/420168772-6dcfd0d2-9142-45d9-b74e-d10aa75073c6.mp4?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NDEzMTgwNTksIm5iZiI6MTc0MTMxNzc1OSwicGF0aCI6Ii82MTIzOTAzMC80MjAxNjg3NzItNmRjZmQwZDItOTE0Mi00NWQ5LWI3NGUtZDEwYWE3NTA3M2M2Lm1wND9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNTAzMDclMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjUwMzA3VDAzMjIzOVomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTdiZjFkNjlmYWNjMmEzOTliM2Y3M2VlYjgyNDRlZDJmOWE3NWZhZjE1MzhiZWY4YmQ3NjdkNTYwYTU5ZDA2MzYmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.UuHQCgWYkh0OQq9qsUWqGsUbhG3i9jcZDAMeHjLt5T4" controls="controls" muted="muted" class="d-block rounded-bottom-2 border-top width-fit" style="max-height:640px; min-height: 200px"></video>

## 설치 방법

두 가지 설치 방법을 제공합니다. **방법 2 (uv 사용)** 이 더 빠른 설치와 효율적인 종속성 관리를 위해 권장됩니다.

### 방법 1: conda 사용

1. 새로운 conda 환경을 생성합니다:

```bash
conda create -n open_manus python=3.12
conda activate open_manus
```

2. 저장소를 클론합니다:

```bash
git clone https://github.com/FoundationAgents/OpenManus.git
cd OpenManus
```

3. 종속성을 설치합니다:

```bash
pip install -r requirements.txt
```

### 방법 2: uv 사용 (권장)

1. uv를 설치합니다. (빠른 Python 패키지 설치 및 종속성 관리 도구):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. 저장소를 클론합니다:

```bash
git clone https://github.com/FoundationAgents/OpenManus.git
cd OpenManus
```

3. 새로운 가상 환경을 생성하고 활성화합니다:

```bash
uv venv --python 3.12
source .venv/bin/activate  # Unix/macOS의 경우
# Windows의 경우:
# .venv\Scripts\activate
```

4. 종속성을 설치합니다:

```bash
uv pip install -r requirements.txt
```

### 브라우저 자동화 도구 (선택사항)

```bash
playwright install
```

## 설정 방법

OpenManus를 사용하려면 사용하는 LLM API에 대한 설정이 필요합니다. 아래 단계를 따라 설정을 완료하세요:

1. `config` 디렉토리에 `config.toml` 파일을 생성하세요 (예제 파일을 복사하여 사용할 수 있습니다):

```bash
cp config/config.example.toml config/config.toml
```

2. `config/config.toml` 파일을 편집하여 API 키를 추가하고 설정을 커스터마이징하세요:

```toml
# 전역 LLM 설정
[llm]
model = "gpt-4o"
base_url = "https://api.openai.com/v1"
api_key = "sk-..."  # 실제 API 키로 변경하세요
max_tokens = 4096
temperature = 0.0

# 특정 LLM 모델에 대한 선택적 설정
[llm.vision]
model = "gpt-4o"
base_url = "https://api.openai.com/v1"
api_key = "sk-..."  # 실제 API 키로 변경하세요
```

## 빠른 시작

OpenManus를 실행하는 한 줄 명령어:

```bash
python main.py
```

이후 터미널에서 아이디어를 작성하세요!

MCP 도구 버전을 사용하려면 다음을 실행하세요:

```bash
python run_mcp.py
```

불안정한 멀티 에이전트 버전을 실행하려면 다음을 실행할 수 있습니다:

```bash
python run_flow.py
```

### 사용자 정의 다중 에이전트 추가

현재 일반 OpenManus 에이전트 외에도 데이터 분석 및 데이터 시각화 작업에 적합한 DataAnalysis 에이전트를 통합했습니다. 이 에이전트를 `config.toml`의 `run_flow`에 추가할 수 있습니다.

```toml
# run-flow에 대한 선택적 구성
[runflow]
use_data_analysis_agent = true     # 기본적으로 비활성화되어 있으며, 활성화하려면 true로 변경
```

또한, 에이전트가 제대로 작동하도록 관련 종속성을 설치해야 합니다: [상세 설치 가이드](app/tool/chart_visualization/README.md##Installation)

## 기여 방법

모든 친절한 제안과 유용한 기여를 환영합니다! 이슈를 생성하거나 풀 리퀘스트를 제출해 주세요.

또는 📧 메일로 연락주세요. @mannaandpoem : mannaandpoem@gmail.com

**참고**: pull request를 제출하기 전에 pre-commit 도구를 사용하여 변경 사항을 확인하십시오. `pre-commit run --all-files`를 실행하여 검사를 실행합니다.

## 커뮤니티 그룹

Feishu 네트워킹 그룹에 참여하여 다른 개발자들과 경험을 공유하세요!

<div align="center" style="display: flex; gap: 20px;">
    <img src="assets/community_group.jpg" alt="OpenManus 交流群" width="300" />
</div>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=FoundationAgents/OpenManus&type=Date)](https://star-history.com/#FoundationAgents/OpenManus&Date)

## 감사의 글

이 프로젝트에 기본적인 지원을 제공해 주신 [anthropic-computer-use](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo)와
[browser-use](https://github.com/browser-use/browser-use)에게 감사드립니다!

또한, [AAAJ](https://github.com/metauto-ai/agent-as-a-judge), [MetaGPT](https://github.com/geekan/MetaGPT), [OpenHands](https://github.com/All-Hands-AI/OpenHands), [SWE-agent](https://github.com/SWE-agent/SWE-agent)에 깊은 감사를 드립니다.

또한 Hugging Face 데모 공간을 지원해 주신 阶跃星辰 (stepfun)에게 감사드립니다.

OpenManus는 MetaGPT 기여자들에 의해 개발되었습니다. 이 에이전트 커뮤니티에 깊은 감사를 전합니다!

## 인용

```bibtex
@misc{openmanus2025,
  author = {Xinbin Liang and Jinyu Xiang and Zhaoyang Yu and Jiayi Zhang and Sirui Hong and Sheng Fan and Xiao Tang},
  title = {OpenManus: An open-source framework for building general AI agents},
  year = {2025},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.15186407},
  url = {https://doi.org/10.5281/zenodo.15186407},
}
```
