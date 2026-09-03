"""
Streamlit dashboard for the AI Coding Practice Browser Agent.

Pages: Dashboard, Problem, Generated Code, Errors, Logs, Memory.
Talks to the FastAPI backend over HTTP. The user must have Chrome running
with --remote-debugging-port and the target problem tab open before using
the "Read Problem" / "Generate Solution" actions.
"""
import httpx
import streamlit as st

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="AI Coding Practice Agent", page_icon="🧠", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "session_state" not in st.session_state:
    st.session_state.session_state = None

st.sidebar.title("🧠 AI Coding Agent")
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Batch Mode", "Problem", "Generated Code", "Errors", "Logs", "Memory"],
)

theme = st.sidebar.toggle("Dark mode", value=True)


def api_get(path: str):
    try:
        resp = httpx.get(f"{API_BASE}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, json_body: dict):
    try:
        resp = httpx.post(f"{API_BASE}{path}", json=json_body, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


# ---------------- Dashboard Page ----------------
if page == "Dashboard":
    st.title("Dashboard")
    col1, col2, col3 = st.columns(3)

    state = st.session_state.session_state
    with col1:
        st.metric("Status", state["status"] if state else "idle")
    with col2:
        st.metric("Retry Count", state["retry_count"] if state else 0)
    with col3:
        st.metric("Max Retries", state["max_retries"] if state else 5)

    st.divider()
    language = st.selectbox("Language", ["python", "java", "cpp", "javascript"])
    max_retries = st.number_input("Max retries", min_value=1, max_value=10, value=5)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("1️⃣ Read & Solve Problem", use_container_width=True):
            with st.spinner("Reading problem and generating solution..."):
                result = api_post(
                    "/solution/generate",
                    {"language": language, "max_retries": max_retries, "session_id": st.session_state.session_id},
                )
                if result:
                    st.session_state.session_id = result["session_id"]
                    st.session_state.session_state = result
                    st.success("Solution pasted into editor. Review, then click 'Run Tests' below.")

    with col_b:
        if st.button("2️⃣ Run Tests", use_container_width=True, disabled=not st.session_state.session_id):
            with st.spinner("Running tests and analyzing results..."):
                result = api_post("/workflow/run-tests", {"session_id": st.session_state.session_id})
                if result:
                    st.session_state.session_state = result
                    if result["status"] == "success":
                        st.balloons()
                        st.success("✅ ALL TESTS PASSED — please review and submit manually!")
                    elif result["status"] == "failed_max_retries":
                        st.error("⚠️ Max retries reached. Manual review needed.")
                    else:
                        st.warning(f"Status: {result['status']} (retry {result['retry_count']})")

    with col_c:
        if st.button("🔄 Reset Session", use_container_width=True):
            st.session_state.session_id = None
            st.session_state.session_state = None
            st.rerun()

    if state and state.get("status") == "success":
        st.success("🎉 All tests passed! Please manually review the code and click Submit in your browser.")


# ---------------- Batch Mode Page ----------------
elif page == "Batch Mode":
    st.title("Batch Mode (Loop)")
    st.caption(
        "Solves multiple problems back-to-back with no manual clicks in between — "
        "language selection, solving, running tests, self-correction, **submission**, "
        "and advancing to the next problem all happen automatically."
    )

    if "batch_id" not in st.session_state:
        st.session_state.batch_id = None

    with st.form("start_batch_form"):
        batch_language = st.selectbox("Language", ["python", "java", "cpp", "javascript"], key="batch_lang")
        batch_max_retries = st.number_input("Max retries per problem", min_value=1, max_value=10, value=5)

        mode = st.radio(
            "How should it move between problems?",
            ["Use site's own 'Next problem' button", "Explicit list of problem URLs"],
        )

        queue: list[str] = []
        max_problems = None
        if mode == "Explicit list of problem URLs":
            urls_text = st.text_area(
                "Problem URLs (one per line)",
                placeholder="https://leetcode.com/problems/two-sum/\nhttps://leetcode.com/problems/valid-parentheses/",
                height=120,
            )
            queue = [line.strip() for line in urls_text.splitlines() if line.strip()]
        else:
            max_problems = st.number_input("Stop after this many problems", min_value=1, max_value=100, value=5)

        submitted = st.form_submit_button("▶️ Start Batch", use_container_width=True)

    if submitted:
        body = {
            "language": batch_language,
            "max_retries": batch_max_retries,
            "queue": queue,
        }
        if max_problems is not None:
            body["max_problems"] = max_problems
        result = api_post("/batch/start", body)
        if result:
            st.session_state.batch_id = result["batch_id"]
            st.success(f"Batch started: {result['batch_id']}")

    if st.session_state.batch_id:
        st.divider()
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Batch: `{st.session_state.batch_id}`")
        with col2:
            if st.button("⏹ Stop Batch", use_container_width=True):
                api_post(f"/batch/stop/{st.session_state.batch_id}", {})
                st.warning("Stop requested — will halt after the current problem finishes.")

        if st.button("🔄 Refresh Status"):
            st.rerun()

        status = api_get(f"/batch/status/{st.session_state.batch_id}")
        if status:
            colA, colB, colC = st.columns(3)
            colA.metric("Status", status["status"])
            colB.metric("Problems done", len(status["results"]))
            colC.metric("Current", status.get("current_url", "—") or "—")

            if status["results"]:
                st.subheader("Results")
                for r in status["results"]:
                    icon = "✅" if r["status"] == "success" else ("⚠️" if r["status"] == "failed_max_retries" else "❌")
                    st.write(f"{icon} **{r.get('title') or r['url']}** — {r['status']} (retries: {r['retry_count']})")
                    if r.get("error_summary"):
                        st.caption(r["error_summary"])

            with st.expander("Batch log"):
                for line in status.get("logs", []):
                    st.text(line)


# ---------------- Problem Page ----------------
elif page == "Problem":
    st.title("Parsed Problem")
    state = st.session_state.session_state
    if state and state.get("problem"):
        problem = state["problem"]
        st.subheader(problem["title"])
        st.caption(f"Difficulty: {problem['difficulty']}")
        st.markdown(problem["description"])
        if problem.get("examples"):
            st.subheader("Examples")
            for i, ex in enumerate(problem["examples"], 1):
                st.code(f"Input: {ex['input']}\nOutput: {ex['output']}", language="text")
        if problem.get("constraints"):
            st.subheader("Constraints")
            for c in problem["constraints"]:
                st.markdown(f"- {c['text']}")
    else:
        st.info("No problem loaded yet. Go to Dashboard and click 'Read & Solve Problem'.")


# ---------------- Generated Code Page ----------------
elif page == "Generated Code":
    st.title("Generated Code")
    state = st.session_state.session_state
    if state and state.get("formatted_code"):
        st.code(state["formatted_code"], language=state.get("language", "python"))
        if state.get("solution", {}).get("explanation"):
            st.info(state["solution"]["explanation"])
        if state.get("plan"):
            plan = state["plan"]
            with st.expander("Algorithm Plan"):
                st.write(f"**Strategy:** {plan['algorithm_strategy']}")
                st.write(f"**Time complexity:** {plan['time_complexity']}")
                st.write(f"**Space complexity:** {plan['space_complexity']}")
                st.write(f"**Edge cases:** {', '.join(plan['edge_cases'])}")
    else:
        st.info("No code generated yet.")


# ---------------- Errors Page ----------------
elif page == "Errors":
    st.title("Errors")
    state = st.session_state.session_state
    if state and state.get("error"):
        error = state["error"]
        st.error(f"**{error['error_type']}**")
        st.code(error["raw_message"])
        if error.get("failed_test_cases"):
            st.subheader("Failed Test Cases")
            for tc in error["failed_test_cases"]:
                st.write(f"Input: `{tc['input']}`")
                st.write(f"Expected: `{tc['expected_output']}` | Actual: `{tc.get('actual_output', 'N/A')}`")
                st.divider()
    else:
        st.info("No errors recorded for the current session.")


# ---------------- Logs Page ----------------
elif page == "Logs":
    st.title("Execution Logs")
    if st.session_state.session_id:
        logs = api_get(f"/logs/{st.session_state.session_id}")
        if logs:
            for entry in logs:
                st.text(f"[{entry['timestamp']}] ({entry['level']}) {entry['step']}: {entry['message']}")
        else:
            st.info("No logs yet.")
    else:
        st.info("Start a session from the Dashboard first.")


# ---------------- Memory Page ----------------
elif page == "Memory":
    st.title("Solved Problems Memory")
    search = st.text_input("Search past solutions")
    solutions = api_get("/memory/solutions")
    if solutions:
        for sol in solutions:
            if search and search.lower() not in sol["explanation"].lower():
                continue
            with st.expander(f"{sol['language']} — {sol['created_at']}"):
                st.code(sol["code"], language=sol["language"])
                st.caption(sol["explanation"])
                st.caption(sol["complexity"])
    else:
        st.info("No solved problems stored yet.")
