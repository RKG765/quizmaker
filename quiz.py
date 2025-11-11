import streamlit as st
import pandas as pd
import time
import datetime
import random
from io import StringIO, BytesIO

# --- 1. Page Configuration and Global Styles ---

st.set_page_config(
    page_title="WARP Quiz",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS for the fixed timer in the top-right corner
TIMER_CSS = """
<style>
.timer-box {{
    position: fixed;
    top: 50px;
    right: 50px;
    background-color: #FF4B4B;
    color: white;
    padding: 10px 20px;
    border-radius: 10px;
    font-size: 20px;
    font-weight: bold;
    z-index: 1000;
    border: 2px solid #B00020;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}}
</style>
<div class="timer-box">{text}</div>
"""

# --- 2. GLOBAL STATE (The "Shared Whiteboard") ---

@st.cache_resource
def get_global_state():
    """
    This function creates a single, shared dictionary that all 
    user sessions can access.
    """
    return {
        "quiz_data": None,
        "quiz_filename": None,
        "quiz_config": {
            "title": "WARP Quiz",
            "num_questions": 10,
            "total_time": 15
        },
        "quiz_active": False,
        "quiz_start_time": None, # Admin's global start
        "leaderboard": pd.DataFrame(columns=["Participant", "Score", "Total", "Time Taken", "Finished At"]),
        "quiz_questions": [],  # The master list of q_ids for this session
    }

# --- 3. SESSION STATE (The "Private Notepad") ---

def initialize_session_state():
    """
    Initializes all PER-USER session state variables.
    These are private to each browser tab.
    """
    defaults = {
        "logged_in": False,
        "role": None,
        # Participant-specific state
        "participant_name": None,
        "participant_start_time": None, # Participant's individual start
        "participant_quiz": [], # The user's randomized list of question dicts
        "current_question_index": 0,
        "participant_answers": {}, # {q_id: selected_option_id}
        "quiz_submitted": False,
        "participant_score": 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- 4. Helper Functions ---

def display_admin_timer(global_state):
    """
    Displays the *elapsed* time on the admin dashboard since
    the quiz was globally started.
    """
    timer_text = "Quiz Inactive"
    if global_state["quiz_active"] and global_state["quiz_start_time"]:
        elapsed_time = time.time() - global_state["quiz_start_time"]
        mins, secs = divmod(int(elapsed_time), 60)
        timer_text = f"Elapsed: {mins:02d}:{secs:02d}"
        
    st.markdown(TIMER_CSS.format(text=timer_text), unsafe_allow_html=True)


def display_participant_timer(global_state):
    """
    Calculates and displays the *remaining* time for the participant.
    Returns the number of seconds remaining.
    """
    remaining_time = -1
    timer_text = "Waiting..."

    # Uses private start time, but global config for duration
    if st.session_state.participant_start_time and not st.session_state.quiz_submitted:
        total_time_sec = global_state["quiz_config"]['total_time'] * 60
        elapsed_time = time.time() - st.session_state.participant_start_time
        remaining_time = total_time_sec - elapsed_time

        if remaining_time <= 0:
            remaining_time = 0
            timer_text = "Time's Up!"
        else:
            mins, secs = divmod(int(remaining_time), 60)
            timer_text = f"⏳ {mins:02d}:{secs:02d}"
    elif st.session_state.quiz_submitted:
        timer_text = "Finished!"
    
    st.markdown(TIMER_CSS.format(text=timer_text), unsafe_allow_html=True)
    return remaining_time


def parse_quiz_file(uploaded_file, global_state):
    """
    Parses the uploaded quiz file and stores it in the GLOBAL state.
    """
    try:
        # (Parsing logic is unchanged)
        lines = uploaded_file.getvalue().decode("utf-8").splitlines()
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and '|' in line and not line.startswith('+') and not line.startswith('-'):
                cleaned_lines.append(line)
        
        if not cleaned_lines:
            st.error("No valid data rows found in file.")
            return
        
        cleaned_data = "\n".join(cleaned_lines)
        data_io = StringIO(cleaned_data)
        df = pd.read_csv(data_io, sep=r'\s*\|\s*', engine='python')
        df.columns = df.columns.str.strip()
        df = df.dropna(axis=1, how='all')
        
        expected_cols = ['question_id', 'question_text', 'difficulty', 'option_id', 'option_text', 'is_correct']
        
        if 'question_id' not in df.columns:
            st.warning("No 'question_id' header found. Assuming first row is data and columns are in order.")
            data_io.seek(0)
            df = pd.read_csv(data_io, sep=r'\s*\|\s*', engine='python', header=None)
            df = df.dropna(axis=1, how='all')
            
            if len(df.columns) == len(expected_cols):
                 df.columns = expected_cols
            else:
                st.error(f"File has {len(df.columns)} columns, but {len(expected_cols)} were expected. Aborting.")
                return

        df = df[expected_cols]
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.strip()
        df = df.dropna(subset=['question_id', 'option_id'])
        df['question_id'] = df['question_id'].astype(str)
        df['option_id'] = df['option_id'].astype(str)
        df['is_correct'] = df['is_correct'].astype(str)

        global_state["quiz_data"] = df
        st.success(f"✅ Successfully loaded {df['question_id'].nunique()} questions.")
        
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        global_state["quiz_data"] = None

def prepare_participant_quiz(global_state):
    """
    Generates a randomized quiz for the participant using the
    GLOBAL question list.
    """
    master_df = global_state["quiz_data"]
    selected_q_ids = global_state["quiz_questions"]
    
    participant_quiz = []
    for q_id in selected_q_ids:
        q_data = master_df[master_df['question_id'] == q_id].copy()
        
        if q_data.empty:
            continue
            
        question_text = q_data['question_text'].iloc[0]
        options = q_data[['option_id', 'option_text', 'is_correct']].to_dict('records')
        random.shuffle(options) 
        
        participant_quiz.append({
            'q_id': q_id, 
            'text': question_text, 
            'options': options
        })
    
    random.shuffle(participant_quiz) 
    
    # Stores the shuffled quiz in the participant's PRIVATE notepad
    st.session_state.participant_quiz = participant_quiz
    st.session_state.participant_answers = {q['q_id']: None for q in participant_quiz}

def submit_quiz(global_state):
    """
    Scores the participant's quiz and adds the result to the
    GLOBAL leaderboard.
    """
    if st.session_state.quiz_submitted:
        return 

    st.session_state.quiz_submitted = True
    score = 0
    total = len(st.session_state.participant_quiz)
    master_df = global_state["quiz_data"]
    
    for q_id, selected_opt_id in st.session_state.participant_answers.items():
        if selected_opt_id is None:
            continue 
        
        try:
            correct_row = master_df[
                (master_df['question_id'] == str(q_id)) & 
                (master_df['is_correct'] == '1')
            ]
            if not correct_row.empty:
                correct_opt_id = correct_row['option_id'].iloc[0]
                if str(selected_opt_id) == str(correct_opt_id):
                    score += 1
            else:
                st.warning(f"Could not find correct answer for Q_ID {q_id} in master file.")
        except Exception as e:
            st.error(f"Error scoring question {q_id}: {e}")

    st.session_state.participant_score = score
    
    # Calculate completion time
    duration_seconds = 0
    if st.session_state.participant_start_time:
         duration_seconds = time.time() - st.session_state.participant_start_time
    duration_formatted = str(datetime.timedelta(seconds=int(duration_seconds)))
    
    # Add to leaderboard
    finish_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame({
        "Participant": [st.session_state.participant_name],
        "Score": [score],
        "Total": [total],
        "Time Taken": [duration_formatted],
        "Finished At": [finish_time]
    })
    
    # Writes the score to the GLOBAL leaderboard
    global_state["leaderboard"] = pd.concat(
        [global_state["leaderboard"], new_entry], 
        ignore_index=True
    )

def show_participant_results(global_state):
    """Displays the final score and leaderboard to the participant."""
    score = st.session_state.participant_score
    total = len(st.session_state.participant_quiz)
    
    st.success(f"## ✅ Quiz Submitted! You scored {score} / {total}")
    st.balloons()
    st.info("You can review your score on the leaderboard below or retake the quiz.")
    
    if st.button("🔄 Retake Quiz", use_container_width=True, type="primary"):
        st.session_state.participant_start_time = time.time()
        st.session_state.current_question_index = 0
        st.session_state.participant_answers = {}
        st.session_state.quiz_submitted = False
        st.session_state.participant_score = 0
        
        prepare_participant_quiz(global_state) # Pass global state in
        
        st.rerun()
    
    st.subheader("Leaderboard")
    display_leaderboard(global_state) # Pass global state in
    st.info("Your score is recorded. You can retake, log out, or close this window.")

def display_leaderboard(global_state):
    """Helper to fetch, format, and display the GLOBAL leaderboard."""
    if not global_state["leaderboard"].empty:
        df_display = global_state["leaderboard"].copy()
        
        df_display = df_display.sort_values(
            by=["Score", "Time Taken"], 
            ascending=[False, True]
        ).reset_index(drop=True)
        
        df_display['Score'] = df_display['Score'].astype(str) + " / " + df_display['Total'].astype(str)
        
        st.dataframe(
            df_display[['Participant', 'Score', 'Time Taken', 'Finished At']], 
            use_container_width=True # This makes it fill the space
        )
    else:
        st.info("No results have been submitted yet.")

# --- 5. Page Views (Login, Admin, Participant) ---

def show_login_screen():
    """Displays the login form in the sidebar."""
    st.sidebar.header("🔐 WARP Login")
    role = st.sidebar.selectbox("Select Your Role", ["Participant", "Admin"])
    
    username = st.sidebar.text_input("Username", placeholder="Enter username")
    password = st.sidebar.text_input("Password", placeholder="Enter password", type="password")
    
    if st.sidebar.button("Login", use_container_width=True):
        if role == "Admin" and username == "admin" and password == "admin123":
            st.session_state.logged_in = True
            st.session_state.role = "admin"
            st.sidebar.success("Admin login successful!")
            st.rerun()
        elif role == "Participant" and username == "student" and password == "pass123":
            st.session_state.logged_in = True
            st.session_state.role = "participant"
            st.sidebar.success("Participant login successful!")
            st.rerun()
        else:
            st.sidebar.error("Invalid credentials. Please try again.")
            
    st.header("Welcome to the WARP Quiz Platform")
    st.info("Please log in using the sidebar to continue.")

def admin_dashboard(global_state):
    """Displays the admin interface for quiz management."""
    st.header("👑 Admin Dashboard")
    display_admin_timer(global_state)
    
    st.sidebar.info(f"Logged in as **Admin**")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.rerun()

    tab1, tab2 = st.tabs(["📊 Quiz Setup & Control", "🏆 Leaderboard"])

    with tab1:
        st.subheader("1. Upload Quiz File")
        
        if global_state["quiz_data"] is None:
            uploaded_file = st.file_uploader(
                "Upload .txt, .tsv, or .csv quiz file (MySQL format)", 
                type=["txt", "tsv", "csv"]
            )
            if uploaded_file:
                parse_quiz_file(uploaded_file, global_state)
                global_state["quiz_filename"] = uploaded_file.name
                st.rerun()
        else:
            st.success(f"✅ File loaded: {global_state['quiz_filename']}")
            if st.button("Remove Uploaded File", type="secondary"):
                global_state["quiz_data"] = None
                global_state["quiz_filename"] = None
                global_state["quiz_active"] = False
                global_state["quiz_start_time"] = None
                st.warning("File removed. Quiz is now inactive.")
                st.rerun()
            
        st.subheader("2. Configure Quiz")
        if global_state["quiz_data"] is not None and not global_state["quiz_data"].empty:
            df = global_state["quiz_data"]
            num_available = df['question_id'].nunique()
            st.info(f"Found {num_available} unique questions in the file.")

            with st.form("quiz_config_form"):
                title = st.text_input("Quiz Title", global_state["quiz_config"]['title'])
                num_q = st.slider(
                    "Number of Questions", 
                    min_value=1, 
                    max_value=num_available, 
                    value=min(global_state["quiz_config"]['num_questions'], num_available)
                )
                total_t = st.number_input(
                    "Total Quiz Time (minutes)", 
                    min_value=1, 
                    max_value=120, 
                    value=global_state["quiz_config"]['total_time']
                )
                
                submitted = st.form_submit_button("Save Configuration")
                if submitted:
                    global_state["quiz_config"] = {
                        "title": title,
                        "num_questions": num_q,
                        "total_time": total_t
                    }
                    st.success("Configuration saved!")
        else:
            st.warning("Please upload a valid quiz file to configure the quiz.")

        st.subheader("3. Control Quiz")
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 START QUIZ", type="primary", use_container_width=True, 
                          disabled=global_state["quiz_active"]):
                if global_state["quiz_data"] is None or global_state["quiz_data"].empty:
                    st.error("Cannot start. Please upload a valid quiz file first.")
                else:
                    # --- Admin writes to the GLOBAL state ---
                    global_state["quiz_active"] = True 
                    global_state["quiz_start_time"] = time.time()
                    global_state["leaderboard"] = pd.DataFrame(columns=["Participant", "Score", "Total", "Time Taken", "Finished At"])
                    
                    all_q_ids = global_state["quiz_data"]['question_id'].unique().tolist()
                    num_to_select = global_state["quiz_config"]['num_questions']
                    global_state["quiz_questions"] = random.sample(all_q_ids, num_to_select)
                    
                    st.success(f"Quiz '{global_state['quiz_config']['title']}' is now ACTIVE!")
                    st.rerun()

        with col2:
            if st.button("⛔ RESET QUIZ", use_container_width=True):
                # --- Admin resets the GLOBAL state ---
                global_state["quiz_active"] = False
                global_state["quiz_start_time"] = None
                global_state["quiz_questions"] = []
                st.warning("Quiz has been reset. All participants disconnected.")
                st.rerun()

    with tab2:
        st.subheader("🏆 Live Leaderboard")
        display_leaderboard(global_state)
        
        if not global_state["leaderboard"].empty:
            csv_buffer = BytesIO()
            global_state["leaderboard"].to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_buffer.seek(0)
            
            st.download_button(
                label="Download Leaderboard as CSV",
                data=csv_buffer,
                file_name=f"warp_leaderboard_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    # --- NEW FEATURE: Admin Auto-Refresh ---
    # This will rerun the admin page every 5 seconds to update the leaderboard
    if global_state["quiz_active"]:
        time.sleep(5)
        st.rerun()

def participant_page(global_state):
    """Displays the participant interface for taking the quiz."""
    st.header(f"🧠 {global_state['quiz_config']['title']}")
    remaining_time = display_participant_timer(global_state)

    st.sidebar.info(f"Logged in as **Participant**")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.rerun()

    # --- State 1: Quiz has been submitted ---
    # This 'return' is critical to prevent the "Next" button from showing
    if st.session_state.quiz_submitted:
        show_participant_results(global_state)
        return 

    # --- State 2: Quiz is not active ---
    if not global_state["quiz_active"]:
        st.info("Please wait for the admin to start the quiz.")
        return
        
    # --- State 3: Time is up (Auto-submit) ---
    if remaining_time == 0 and not st.session_state.quiz_submitted:
        st.warning("Time's up! Auto-submitting your quiz...")
        submit_quiz(global_state)
        st.rerun()

    # --- State 4: Enter name to join ---
    if not st.session_state.participant_name:
        st.subheader(f"Welcome to the '{global_state['quiz_config']['title']}' Quiz!")
        name = st.text_input("Please enter your name to begin:")
        if st.button("Join Quiz") and name:
            st.session_state.participant_name = name
            st.session_state.current_question_index = 0
            st.session_state.quiz_submitted = False
            st.session_state.participant_start_time = time.time() 
            prepare_participant_quiz(global_state)
            st.rerun()
        return

    # --- State 5: Take the quiz ---
    if st.session_state.participant_name and st.session_state.participant_quiz:
        total_questions = len(st.session_state.participant_quiz)
        q_index = st.session_state.current_question_index

        if q_index >= total_questions:
            st.warning("Submitting quiz...")
            submit_quiz(global_state)
            st.rerun()
            return
            
        current_q = st.session_state.participant_quiz[q_index]
        q_id = current_q['q_id']
        q_text = current_q['text']
        options = current_q['options']
        
        st.subheader(f"Question {q_index + 1} of {total_questions}")
        st.markdown(f"### {q_text}")
        
        option_texts = [opt['option_text'] for opt in options]
        stored_answer_id = st.session_state.participant_answers.get(q_id)
        default_index = None
        if stored_answer_id:
            for i, opt in enumerate(options):
                if opt['option_id'] == stored_answer_id:
                    default_index = i
                    break
        
        selected_option_text = st.radio(
            "Choose your answer:", 
            option_texts, 
            index=default_index, 
            key=f"q_{q_id}"
        )
        
        selected_option_id = None
        for opt in options:
            if opt['option_text'] == selected_option_text:
                selected_option_id = opt['option_id']
                break
        
        if selected_option_id:
            st.session_state.participant_answers[q_id] = selected_option_id

        st.markdown("---")
        
        col1, col_spacer, col2 = st.columns([0.4, 0.2, 0.4])
        
        with col1:
            if q_index > 0:
                if st.button("⬅️ Previous", use_container_width=True):
                    st.session_state.current_question_index -= 1
                    st.rerun()
        
        with col2:
            if q_index < total_questions - 1:
                if st.button("Next ➡️", use_container_width=True):
                    st.session_state.current_question_index += 1
                    st.rerun()
            else:
                if st.button("🏁 SUBMIT QUIZ", type="primary", use_container_width=True):
                    submit_quiz(global_state)
                    st.rerun()

    # --- Auto-refresh loop for the timer ---
    if st.session_state.participant_start_time and not st.session_state.quiz_submitted:
        if remaining_time > 0:
            time.sleep(1)
            st.rerun()


# --- 6. Main Application Logic ---

def main():
    """Main function to run the app."""
    st.title("🚀 WARP — Web-Accessible Rapid Platform 🚀")
    
    # Get the "shared whiteboard" for all users
    global_state = get_global_state()
    
    # Get the "private notepad" for this specific user
    initialize_session_state()

    # Routing
    if not st.session_state.logged_in:
        show_login_screen()
    elif st.session_state.role == "admin":
        admin_dashboard(global_state)
    elif st.session_state.role == "participant":
        participant_page(global_state)

if __name__ == "__main__":
    main()