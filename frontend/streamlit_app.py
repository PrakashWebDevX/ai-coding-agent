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
    ["Dashboard", "Problem", "Generated Code", "Errors", "Logs", "Memory"],
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
