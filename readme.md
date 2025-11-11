WARP — Web-Accessible Rapid Platform 🚀
WARP is a simple, self-contained quiz application for LAN environments, built entirely in a single Python file using Streamlit. It allows a host (Admin) to run a live, timed quiz for multiple participants (Students) on the same local network.

✨ Features
Multi-User & LAN-Ready: Host on one machine, participants connect from any device (phone, laptop, tablet) on the same network.

Two-Role System: Secure Admin dashboard for quiz control and a separate Participant view for taking the test.

Dynamic Quiz Upload: Admin can upload any quiz file in the correct format.

Persistent File: The uploaded quiz file stays loaded and ready until the Admin manually removes it.

Per-Participant Timers: Each participant's countdown starts when they join the quiz, not when the admin starts it.

Live Ticking Countdown: The timer visibly ticks down every second for the participant.

Randomization: Questions and their corresponding options are randomized for each participant to reduce cheating.

Live Leaderboard: Scores and completion times (e.g., "0:05:32") are updated in real-time as participants finish.

Auto-Submission: Quizzes are automatically submitted when the timer runs out.

CSV Export: Admin can download the final leaderboard as a CSV file.

Self-Contained: Runs from a single Python file with minimal dependencies.

🏁 Getting Started
Prerequisites
You must have Python 3.6 or newer installed.

You must be on the same Local Area Network (LAN) or Wi-Fi as all other participants.

1. Installation
Save the warp_quiz.py file to a folder on your computer.

Open your terminal or command prompt and install the required Python libraries:

Bash

pip install streamlit pandas
2. Running the App (Host Machine)
In your terminal, navigate to the directory where you saved warp_quiz.py.

Run the following command:

Bash

streamlit run warp_quiz.py
Your browser will automatically open to http://localhost:8501. This is the Admin/Host view.

🕹️ How to Use
🔐 1. Login Credentials
Admin (Host):

Username: admin

Password: admin123

Participant (Student):

Username: student

Password: pass123

👑 2. Admin (Host) Flow
Log in with the Admin credentials.

Go to the "📊 Quiz Setup & Control" tab.

Upload your quiz file (see format below). The file will stay loaded until you click "Remove Uploaded File."

Configure the Quiz Title, Number of Questions, and Total Time (in minutes) for each participant.

Click "🚀 START QUIZ". The quiz is now available for participants to join.

Monitor the "🏆 Leaderboard" tab as participants submit their results.

After the quiz, you can download the leaderboard as a CSV.

Click "⛔ RESET QUIZ" to stop the session and disconnect all users.

🧠 3. Participant (Student) Flow
Find the Host's IP Address: The Admin must find their computer's local IP address.

On Windows: Open Command Prompt and type ipconfig. Look for the "IPv4 Address".

On Mac/Linux: Open Terminal and type ifconfig or ip addr show. Look for the inet address.

(It will look like 192.--.--.--).

Connect to the App: On their device (phone, laptop), the participant must open a web browser and go to the Host's IP address, followed by port :8501.

Example: http://192.-.-.-:8501

Log in with the Participant credentials.

Enter their name and click "Join Quiz".

Their personal timer starts now.

Answer the questions. They can navigate with "Next" and "Previous" buttons.

Click "🏁 SUBMIT QUIZ" when finished or let the timer auto-submit.

View their final score and the live leaderboard.

📁 Quiz File Format
The app accepts .txt, .tsv, or .csv files that are pipe-separated (|). This format is similar to a MySQL command-line export. The file parser is robust and will ignore border lines (like +--+) and empty lines.

Crucial: The file must contain these exact column headers, even if you don't use all of them: question_id | question_text | difficulty | option_id | option_text | is_correct

question_id: A unique ID for each question. All options for the same question share this ID.

option_id: A unique ID for each option.

is_correct: Use 1 for the correct answer and 0 for all incorrect answers.

Example quiz.txt
You can copy the text below and save it as quiz.txt to test the application.

+-----------------+---------------------------------------+------------+-------------+---------------+--------------+
| question_id 	| question_text                     	| difficulty | option_id | option_text   | is_correct |
+-----------------+---------------------------------------+------------+-------------+---------------+--------------+
| 1           	| What is 2+2?                          	| easy   	| 10        | 3         	| 0        	|
| 1           	| What is 2+2?                          	| easy   	| 11        | 4         	| 1        	|
| 1           	| What is 2+2?                          	| easy   	| 12        | 5         	| 0        	|
| 2           	| What is the capital of France?        	| easy   	| 20        | London    	| 0        	|
| 2           	| What is the capital of France?        	| easy   	| 21        | Berlin    	| 0        	|
| 2           	| What is the capital of France?        	| easy   	| 22        | Paris     	| 1        	|
| 2           	| What is the capital of France?        	| easy   	| 23        | Madrid    	| 0        	|
| 3           	| What library is this app built with?  	| medium 	| 30        | Streamlit 	| 1        	|
| 3           	| What library is this app built with?  	| medium 	| 31        | Django    	| 0        	|
| 3           	| What library is this app built with?  	| medium 	| 32        | Flask     	| 0        	|
| 4           	| What does 'LAN' stand for?            	| medium 	| 40        | Local Area Network | 1       	|
| 4           	| What does 'LAN' stand for?            	| medium 	| 41        | Long Area Network | 0        	|
| 5           	| Which of these is a pandas function?  	| hard   	| 50        | st.write  	| 0        	|
| 5           	| Which of these is a pandas function?  	| hard   	| 51        | pd.read_csv 	| 1        	|
| 5           	| Which of these is a pandas function?  	| hard   	| 52        | time.time 	| 0        	|
+-----------------+---------------------------------------+------------+-------------+---------------+--------------+
⚠️ Troubleshooting
Problem: Participants see "Site Can't Be Reached" or "Connection Timed Out" when trying to connect to the host's IP address.

Solution: This is almost always a firewall issue on the Host (Admin's) computer.

The Host's firewall is blocking other devices from connecting. You must create a new Inbound Rule to Allow connections on TCP Port 8501.

On Windows: Go to "Windows Defender Firewall with Advanced Security" > "Inbound Rules" > "New Rule..."

On macOS: Go to "System Preferences" > "Security & Privacy" > "Firewall" > "Firewall Options..." and add Python or Streamlit to allow incoming connections.