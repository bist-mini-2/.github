import os
import sys
import json
import urllib.request
import urllib.error
import time

def main():
    gemini_key = os.environ.get("GEMINI_API_KEY")
    github_token = os.environ.get("GITHUB_TOKEN")
    pr_number = os.environ.get("PR_NUMBER")
    repository = os.environ.get("REPOSITORY")
    pr_author = os.environ.get("PR_AUTHOR")
    diff_file = "pr.diff"

    if not gemini_key:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)
    if not pr_number or not repository:
        print("Error: PR_NUMBER or REPOSITORY environment variable is not set.")
        sys.exit(1)

    # Read git diff
    if not os.path.exists(diff_file):
        print(f"Error: Diff file {diff_file} not found.")
        sys.exit(1)

    with open(diff_file, "r", encoding="utf-8", errors="ignore") as f:
        diff_content = f.read()

    if not diff_content.strip():
        print("Warning: Diff is empty. Skipping PR description generation.")
        sys.exit(0)

    # Truncate diff if it's exceptionally large to avoid API request payload size limit (approx 2MB limit on request body)
    if len(diff_content) > 150000:
        print("Warning: Diff is large. Truncating to 150KB.")
        diff_content = diff_content[:150000] + "\n\n[... Diff truncated due to size limit ...]"

    # Prepare system prompt for Gemini
    system_prompt = (
        "You are an expert software engineer and code reviewer.\n"
        "Your task is to analyze the provided git diff and generate a pull request (PR) description in Korean.\n"
        "You must fill in the following template exactly as it is structured.\n"
        "For the PR Type section, mark selected types with '☑' instead of '☐' (e.g. - ☑ instead of - ☐).\n"
        "For the Verification Checklist, mark completed items with '[x]' instead of '[ ]' (e.g. - [x] instead of - [ ]).\n\n"
        "Here is the PR template structure you must follow:\n"
        "```markdown\n"
        "## 📌 작업 개요 (PR Type)\n"
        "<!-- 작업 내용에 해당하는 유형에 ☐를 ☑로 표시해 주세요. -->\n"
        "- ☐ 새로운 기능 추가 (Feature)\n"
        "- ☐ 버그 수정 (Bug Fix)\n"
        "- ☐ 코드 리팩터링 (Refactor)\n"
        "- ☐ UI/스타일 작업 (Design)\n"
        "- ☐ 문서 수정/추가 (Docs)\n"
        "- ☐ 테스트 코드 추가 (Test)\n"
        "- ☐ 기타/설정 변경 (Chore)\n"
        "\n"
        "---\n"
        "\n"
        "## 📝 작업 내용 (Description)\n"
        "<!-- 이번 PR에서 변경된 핵심 내용을 간략하게 설명해 주세요. -->\n"
        "- [핵심 변경사항 요약]\n"
        "- [주요 변경사항 2]\n"
        "\n"
        "---\n"
        "\n"
        "## 🔗 연관 이슈 (Related Issues)\n"
        "<!-- 해결된 이슈 번호가 있다면 적어주세요. 예: Closes #123 -->\n"
        "- Closes #\n"
        "\n"
        "---\n"
        "\n"
        "## 🧪 테스트 및 검증 (Verification Checklist)\n"
        "<!-- PR 병합 전에 아래 사항들을 모두 확인했는지 체크해 주세요. -->\n"
        "- [x] 개발 환경에서 빌드 및 컴파일에 성공했나요? (기본 체크)\n"
        "- [ ] 작업한 기능에 대한 테스트를 진행했거나 테스트 코드를 작성했나요?\n"
        "- [x] 불필요한 콘솔 로그(`console.log`, `print` 등)나 주석을 제거했나요? (기본 체크)\n"
        "- [x] 코드 스타일 가이드(eslint, prettier 등)를 준수했나요? (기본 체크)\n"
        "```\n\n"
        "Rules:\n"
        "1. Identify the PR Type based on the diff and mark '☑' instead of '☐' accordingly (can check multiple if appropriate).\n"
        "2. Keep the 'Description' concise, clear, and professional in Korean.\n"
        "3. For the checkboxes under '🧪 테스트 및 검증', if the diff contains test files (e.g. tests/, test_*.py, *.test.js, Spec), check the test box with '[x]' as well.\n"
        "4. Do not include markdown code block syntax (like ```markdown) around the generated template. Just output the raw markdown content directly.\n"
        "5. Leave the 'Related Issues' as placeholders for the user to edit if needed."
    )

    # Call Gemini API
    # Endpoint for Gemini 2.5 Flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{system_prompt}\n\nHere is the git diff to analyze:\n\n{diff_content}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }

    fallback_template = (
        "## 📌 작업 개요 (PR Type)\n"
        "<!-- 작업 내용에 해당하는 유형에 ☐를 ☑로 표시해 주세요. -->\n"
        "- ☐ 새로운 기능 추가 (Feature)\n"
        "- ☐ 버그 수정 (Bug Fix)\n"
        "- ☐ 코드 리팩터링 (Refactor)\n"
        "- ☐ UI/스타일 작업 (Design)\n"
        "- ☐ 문서 수정/추가 (Docs)\n"
        "- ☐ 테스트 코드 추가 (Test)\n"
        "- ☐ 기타/설정 변경 (Chore)\n\n"
        "---\n\n"
        "## 📝 작업 내용 (Description)\n"
        "<!-- 이번 PR에서 변경된 핵심 내용을 간략하게 설명해 주세요. -->\n"
        "- \n\n"
        "---\n\n"
        "## 🔗 연관 이슈 (Related Issues)\n"
        "<!-- 해결된 이슈 번호가 있다면 적어주세요. 예: Closes #123 -->\n"
        "- Closes #\n\n"
        "---\n\n"
        "## 🧪 테스트 및 검증 (Verification Checklist)\n"
        "<!-- PR 병합 전에 아래 사항들을 모두 확인했는지 체크해 주세요. -->\n"
        "- [ ] 개발 환경에서 빌드 및 컴파일에 성공했나요?\n"
        "- [ ] 작업한 기능에 대한 테스트를 진행했거나 테스트 코드를 작성했나요?\n"
        "- [ ] 불필요한 콘솔 로그(`console.log`, `print` 등)나 주석을 제거했나요?\n"
        "- [ ] 코드 스타일 가이드(eslint, prettier 등)를 준수했나요?\n"
    )

    generated_text = None
    max_retries = 3
    retry_delay = 2 # seconds
    is_fallback = False

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                generated_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                print("Gemini response generated successfully.")
                break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            print(f"HTTP Error calling Gemini API (Attempt {attempt}): {e.code} - {err_body}")
            if e.code in [429, 503, 500, 504] and attempt < max_retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                break
        except Exception as e:
            print(f"Unexpected error calling Gemini API (Attempt {attempt}): {e}")
            if attempt < max_retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                break

    if not generated_text:
        print("Warning: Failed to generate PR description after retries. Falling back to the empty template.")
        generated_text = fallback_template
        is_fallback = True

    # Update Pull Request body via GitHub API
    # PATCH /repos/{owner}/{repo}/pulls/{pull_number}
    github_api_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}"
    patch_payload = {
        "body": generated_text
    }
    
    req_github = urllib.request.Request(
        github_api_url,
        data=json.dumps(patch_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        },
        method="PATCH"
    )

    try:
        with urllib.request.urlopen(req_github) as response:
            print("Successfully updated Pull Request description on GitHub.")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error updating PR description: {e.code} - {e.read().decode('utf-8')}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error updating PR description: {e}")
        sys.exit(1)

    # Post a comment to trigger GitHub mobile notification
    if pr_author:
        comment_url = f"https://api.github.com/repos/{repository}/issues/{pr_number}/comments"
        
        if is_fallback:
            comment_body = f"⚠️ @pileuszu @{pr_author} Gemini API 일시적 오류(503)로 인해 기본 템플릿으로 생성되었습니다. PR 내용을 수동으로 기재해 주세요."
        else:
            comment_body = f"🤖 @pileuszu @{pr_author} PR 분석 및 본문 작성이 완료되었습니다! 변경 사항을 확인하고 피드백해 주세요."
            
        comment_payload = {
            "body": comment_body
        }
        req_comment = urllib.request.Request(
            comment_url,
            data=json.dumps(comment_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req_comment) as response:
                print("Successfully posted notification comment on Pull Request.")
        except Exception as e:
            print(f"Warning: Failed to post notification comment: {e}")

if __name__ == "__main__":
    main()
