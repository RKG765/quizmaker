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
# (Corrected with double curly braces {{ }} for CSS)
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

# --- 2. Session State Initialization ---

def initialize_session_state():
    """Initializes all required session state variables."""
    defaults = {
        "logged_in": False,
        "role": None,
        "quiz_data": None,
        "quiz_filename": None, # For persistent upload
        "quiz_config": {
            "title": "WARP Quiz",
            "num_questions": 10,
            "total_time": 15
        },
        "quiz_active": False,
        "quiz_start_time": None, # Admin's global start
        "leaderboard": pd.DataFrame(columns=["Participant", "Score", "Total", "Time Taken", "Finished At"]),
        "quiz_questions": [],  # The master list of q_ids for this session
        
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

# --- 3. Helper Functions ---

def display_admin_timer():
    """
    Displays the *elapsed* time on the admin dashboard since
    the quiz was globally started.
    """
    timer_text = "Quiz Inactive"
    if st.session_state.quiz_active and st.session_state.quiz_start_time:
        elapsed_time = time.time() - st.session_state.quiz_start_time
        mins, secs = divmod(int(elapsed_time), 60)
        timer_text = f"Elapsed: {mins:02d}:{secs:02d}"
        
    st.markdown(TIMER_CSS.format(text=timer_text), unsafe_allow_html=True)


def display_participant_timer():
    """
    Calculates and displays the *remaining* time for the participant.
    Returns the number of seconds remaining.
    """
    remaining_time = -1
    timer_text = "Waiting..."

    if st.session_state.participant_start_time and not st.session_state.quiz_submitted:
        total_time_sec = st.session_state.quiz_config['total_time'] * 60
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


def parse_quiz_file(uploaded_file):
    """
    Parses the uploaded quiz file (txt, tsv, or csv) robustly.
    Handles MySQL export format with '|' separators and junk lines.
    """
    try:
        # Read as text, filter junk
        lines = uploaded_file.getvalue().decode("utf-8").splitlines()
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            # Keep lines that have a pipe and aren't borders
            if line and '|' in line and not line.startswith('+') and not line.startswith('-'):
                cleaned_lines.append(line)
        
        if not cleaned_lines:
            st.error("No valid data rows found in file.")
            return

        # Re-create a file-like object from cleaned lines
        cleaned_data = "\n".join(cleaned_lines)
        data_io = StringIO(cleaned_data)

        # Use pandas to read the cleaned data, assuming a '|' separator
        # The regex handles whitespace around the pipe
        df = pd.read_csv(data_io, sep=r'\s*\|\s*', engine='python')
        
        # Clean column headers
        df.columns = df.columns.str.strip()
        
        # Drop fully empty columns that might result from leading/trailing pipes
        df = df.dropna(axis=1, how='all')
        
        # Check if headers are present. If not, reload and assign them.
        expected_cols = ['question_id', 'question_text', 'difficulty', 'option_id', 'option_text', 'is_correct']
        
        if 'question_id' not in df.columns:
            st.warning("No 'question_id' header found. Assuming first row is data and columns are in order.")
            data_io.seek(0) # Reset buffer
            df = pd.read_csv(data_io, sep=r'\s*\|\s*', engine='python', header=None)
            df = df.dropna(axis=1, how='all')
            
            # Assign column names based on expected number
            if len(df.columns) == len(expected_cols):
                 df.columns = expected_cols
            else:
                st.error(f"File has {len(df.columns)} columns, but {len(expected_cols)} were expected. Aborting.")
                return

        # Ensure we only have the columns we need
        df = df[expected_cols]
        
        # Clean all string data
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.strip()
        
        # Drop rows where essential IDs are missing
        df = df.dropna(subset=['question_id', 'option_id'])
        
        # Convert types for safety
        df['question_id'] = df['question_id'].astype(str)
        df['option_id'] = df['option_id'].astype(str)
        df['is_correct'] = df['is_correct'].astype(str)

        st.session_state.quiz_data = df
        st.success(f"✅ Successfully loaded {df['question_id'].nunique()} questions.")
        
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        st.session_state.quiz_data = None

def prepare_participant_quiz():
    """
    Generates a randomized quiz (questions and options) for the
    currently logged-in participant.
    """
    master_df = st.session_state.quiz_data
    # Get the master list of question IDs selected by the admin
    selected_q_ids = st.session_state.quiz_questions
    
    participant_quiz = []
    for q_id in selected_q_ids:
        q_data = master_df[master_df['question_id'] == q_id].copy()
        
        if q_data.empty:
            continue
            
        question_text = q_data['question_text'].iloc[0]
        # Get options as a list of dicts
        options = q_data[['option_id', 'option_text', 'is_correct']].to_dict('records')
        
        # Randomize option order
        random.shuffle(options) 
        
        participant_quiz.append({
            'q_id': q_id, 
            'text': question_text, 
            'options': options
        })
    
    # Randomize question order
    random.shuffle(participant_quiz) 
    
    st.session_state.participant_quiz = participant_quiz
    # Initialize answers dict with None
    st.session_state.participant_answers = {q['q_id']: None for q in participant_quiz}

def submit_quiz():
    """
    Scores the participant's quiz and adds the result to the leaderboard.
    """
    if st.session_state.quiz_submitted:
        return # Prevent double submission

    st.session_state.quiz_submitted = True
    score = 0
    total = len(st.session_state.participant_quiz)
    master_df = st.session_state.quiz_data
    
    for q_id, selected_opt_id in st.session_state.participant_answers.items():
        if selected_opt_id is None:
            continue # Unanswered
        
        try:
            # Find the correct answer from the master dataframe
            # We compare 'is_correct' as a string '1' for robustness
            correct_row = master_df[
                (master_df['question_id'] == str(q_id)) & 
                (master_df['is_correct'] == '1')
            ]
            
            if not correct_row.empty:
                correct_opt_id = correct_row['option_id'].iloc[0]
                
                # Compare selected ID with correct ID (as strings)
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
    duration_formatted = str(datetime.timedelta(seconds=int(duration_seconds))) # Format as HH:MM:SS
    
    # Add to leaderboard
    finish_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame({
        "Participant": [st.session_state.participant_name],
        "Score": [score],
        "Total": [total],
        "Time Taken": [duration_formatted],
        "Finished At": [finish_time]
    })
    
    # Use pd.concat for safe appending
    st.session_state.leaderboard = pd.concat(
        [st.session_state.leaderboard, new_entry], 
        ignore_index=True
    )

def show_participant_results():
    """Displays the final score and leaderboard to the participant."""
    score = st.session_state.participant_score
    total = len(st.session_state.participant_quiz)
    
    st.success(f"## ✅ Quiz Submitted! You scored {score} / {total}")
    st.balloons()
    
    st.subheader("Leaderboard")
    display_leaderboard()
    st.info("You can now close this window. Your score is recorded.")

def display_leaderboard():
    """Helper to fetch, format, and display the leaderboard."""
    if 'leaderboard' in st.session_state and not st.session_state.leaderboard.empty:
        df_display = st.session_state.leaderboard.copy()
        
        # Sort by score (highest first)
        df_display = df_display.sort_values(by="Score", ascending=False).reset_index(drop=True)
        
        # Create a formatted score column for display
        df_display['Score'] = df_display['Score'].astype(str) + " / " + df_display['Total'].astype(str)
        
        # Display the relevant columns
        st.dataframe(
            df_display[['Participant', 'Score', 'Time Taken', 'Finished At']], 
            use_container_width=True
        )
    else:
        st.info("No results have been submitted yet.")

# --- 4. Page Views (Login, Admin, Participant) ---

def show_login_screen():
    """Displays the login form in the sidebar."""
    st.sidebar.header("🔐 WARP Login")
    role = st.sidebar.selectbox("Select Your Role", ["Participant", "Admin"])
    
    # Removed default values to prevent autofill
    username = st.sidebar.text_input("Username", placeholder="Enter username")
    password = st.sidebar.text_input("Password", placeholder="Enter password", type="password")
    
    if st.sidebar.button("Login", use_container_width=True):
        # Admin Login
        if role == "Admin" and username == "admin" and password == "admin123":
            st.session_state.logged_in = True
            st.session_state.role = "admin"
            st.sidebar.success("Admin login successful!")
            st.rerun()
        # Participant Login
        elif role == "Participant" and username == "student" and password == "pass123":
            st.session_state.logged_in = True
            st.session_state.role = "participant"
            st.sidebar.success("Participant login successful!")
            st.rerun()
        else:
            st.sidebar.error("Invalid credentials. Please try again.")
            
    st.header("Welcome to the WARP Quiz Platform")
    st.info("Please log in using the sidebar to continue.")

def admin_dashboard():
    """Displays the admin interface for quiz management."""
    st.header("👑 Admin Dashboard")
    display_admin_timer()
    
    st.sidebar.info(f"Logged in as **Admin**")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.rerun()

    tab1, tab2 = st.tabs(["📊 Quiz Setup & Control", "🏆 Leaderboard"])

    with tab1:
        st.subheader("1. Upload Quiz File")
        
        if st.session_state.quiz_data is None:
            uploaded_file = st.file_uploader(
                "Upload .txt, .tsv, or .csv quiz file (MySQL format)", 
                type=["txt", "tsv", "csv"]
            )
            if uploaded_file:
                # Parse the file and store in session state
                parse_quiz_file(uploaded_file)
                st.session_state.quiz_filename = uploaded_file.name
                st.rerun()
        else:
            st.success(f"✅ File loaded: {st.session_state.quiz_filename}")
            if st.button("Remove Uploaded File", type="secondary"):
                st.session_state.quiz_data = None
                st.session_state.quiz_filename = None
                st.session_state.quiz_active = False # Safety reset
                st.session_state.quiz_start_time = None
                st.warning("File removed. Quiz is now inactive.")
                st.rerun()
            
        st.subheader("2. Configure Quiz")
        if st.session_state.quiz_data is not None and not st.session_state.quiz_data.empty:
            df = st.session_state.quiz_data
            num_available = df['question_id'].nunique()
            st.info(f"Found {num_available} unique questions in the file.")

            # Form for quiz config
            with st.form("quiz_config_form"):
                title = st.text_input("Quiz Title", st.session_state.quiz_config['title'])
                num_q = st.slider(
                    "Number of Questions", 
                    min_value=1, 
                    max_value=num_available, 
                    value=min(st.session_state.quiz_config['num_questions'], num_available)
                )
                total_t = st.number_input(
                    "Total Quiz Time (minutes)", 
                    min_value=1, 
                    max_value=120, 
                    value=st.session_state.quiz_config['total_time']
                )
                
                submitted = st.form_submit_button("Save Configuration")
                if submitted:
                    st.session_state.quiz_config = {
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
                          disabled=st.session_state.quiz_active):
                if st.session_state.quiz_data is None or st.session_state.quiz_data.empty:
                    st.error("Cannot start. Please upload a valid quiz file first.")
                else:
                    # Reset all participant states and start the quiz
                    st.session_state.quiz_active = True
                    st.session_state.quiz_start_time = time.time()
                    st.session_state.leaderboard = pd.DataFrame(columns=["Participant", "Score", "Total", "Time Taken", "Finished At"])
                    st.session_state.participant_name = None
                    st.session_state.participant_quiz = []
                    st.session_state.current_question_index = 0
                    st.session_state.participant_answers = {}
                    st.session_state.quiz_submitted = False
                    st.session_state.participant_start_time = None
                    
                    # Generate the master question set for this session
                    all_q_ids = st.session_state.quiz_data['question_id'].unique().tolist()
                    num_to_select = st.session_state.quiz_config['num_questions']
                    st.session_state.quiz_questions = random.sample(all_q_ids, num_to_select)
                    
                    st.success(f"Quiz '{st.session_state.quiz_config['title']}' is now ACTIVE!")
                    st.rerun()

        with col2:
            if st.button("⛔ RESET QUIZ", use_container_width=True):
                st.session_state.quiz_active = False
                st.session_state.quiz_start_time = None
                st.session_state.quiz_questions = []
                st.warning("Quiz has been reset. All participants disconnected.")
                st.rerun()

    with tab2:
        st.subheader("🏆 Live Leaderboard")
        display_leaderboard()
        
        if not st.session_state.leaderboard.empty:
            # Create CSV data for download
            csv_buffer = BytesIO()
            st.session_state.leaderboard.to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_buffer.seek(0)
            
            st.download_button(
                label="Download Leaderboard as CSV",
                data=csv_buffer,
                file_name=f"warp_leaderboard_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )

def participant_page():
    """Displays the participant interface for taking the quiz."""
    st.header(f"🧠 {st.session_state.quiz_config['title']}")
    remaining_time = display_participant_timer()

    st.sidebar.info(f"Logged in as **Participant**")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.rerun()

    # --- State 1: Quiz has been submitted ---
    if st.session_state.quiz_submitted:
        show_participant_results()
        return

    # --- State 2: Quiz is not active ---
    if not st.session_state.quiz_active:
        st.info("Please wait for the admin to start the quiz.")
        return
        
    # --- State 3: Time is up (Auto-submit) ---
    if remaining_time == 0 and not st.session_state.quiz_submitted:
        st.warning("Time's up! Auto-submitting your quiz...")
        submit_quiz()
        st.rerun()

    # --- State 4: Enter name to join ---
    if not st.session_state.participant_name:
        st.subheader(f"Welcome to the '{st.session_state.quiz_config['title']}' Quiz!")
        name = st.text_input("Please enter your name to begin:")
        if st.button("Join Quiz") and name:
            st.session_state.participant_name = name
            st.session_state.current_question_index = 0
            st.session_state.quiz_submitted = False
            # Participant's individual timer starts NOW
            st.session_state.participant_start_time = time.time() 
            # Generate this specific participant's randomized quiz
            prepare_participant_quiz()
            st.rerun()
        return

    # --- State 5: Take the quiz ---
    if st.session_state.participant_name and st.session_state.participant_quiz:
        total_questions = len(st.session_state.participant_quiz)
        q_index = st.session_state.current_question_index

        # Safety check for index errors
        if q_index >= total_questions:
            st.warning("Submitting quiz...")
            submit_quiz()
            st.rerun()
            return
            
        current_q = st.session_state.participant_quiz[q_index]
        q_id = current_q['q_id']
        q_text = current_q['text']
        options = current_q['options'] # These are already randomized
        
        st.subheader(f"Question {q_index + 1} of {total_questions}")
        st.markdown(f"### {q_text}")
        
        # Get list of option texts for the radio button
        option_texts = [opt['option_text'] for opt in options]
        
        # Find the default index for the radio button (what they selected before)
        stored_answer_id = st.session_state.participant_answers.get(q_id)
        default_index = None
        if stored_answer_id:
            for i, opt in enumerate(options):
                if opt['option_id'] == stored_answer_id:
                    default_index = i
                    break
        
        # Display the radio button
        selected_option_text = st.radio(
            "Choose your answer:", 
            option_texts, 
            index=default_index, 
            key=f"q_{q_id}"
        )
        
        # Find the option_id that corresponds to the selected text
        selected_option_id = None
        for opt in options:
            if opt['option_text'] == selected_option_text:
                selected_option_id = opt['option_id']
                break
        
        # Store the answer (option_id) in session state *immediately*
        if selected_option_id:
            st.session_state.participant_answers[q_id] = selected_option_id

        st.markdown("---")
        
        # Navigation Buttons
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
                # This is the last question
                if st.button("🏁 SUBMIT QUIZ", type="primary", use_container_width=True):
                    submit_quiz()
                    st.rerun()

    # --- Auto-refresh loop for the timer ---
    # This runs only for a logged-in participant who has started and not submitted
    if st.session_state.participant_start_time and not st.session_state.quiz_submitted:
        if remaining_time > 0:
            time.sleep(1)
            st.rerun()


# --- 5. Main Application Logic ---

def main():
    """Main function to run the app."""
    st.title("🚀 WARP — Web-Accessible Rapid Platform 🚀")
    
    # Ensure session state is ready
    initialize_session_state()

    # Routing
    if not st.session_state.logged_in:
        show_login_screen()
    elif st.session_state.role == "admin":
        admin_dashboard()
    elif st.session_state.role == "participant":
        participant_page()

if __name__ == "__main__":
    main()