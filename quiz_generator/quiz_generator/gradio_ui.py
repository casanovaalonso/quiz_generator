import gradio as gr
import requests
import json
import time
from datetime import datetime
import uuid

API_URL = "http://localhost:5000/generate-quiz"

# Store the current quiz data for student mode
quiz_state = {"current_quiz": None, "student_answers": {}, "quiz_id": None}


def generate_quiz_stream(
    learning_objective, num_questions, enable_validation, subject_area, interface_mode
):
    """
    Generator function to provide immediate feedback while the LLM is 'thinking'.
    """
    # Reset quiz state for new quiz generation
    quiz_state["current_quiz"] = None
    quiz_state["student_answers"] = {}
    quiz_state["quiz_id"] = str(uuid.uuid4())[:8]  # Generate a unique ID for this quiz

    # First, immediately yield a "thinking" message with timestamp
    current_time = datetime.now().strftime("%H:%M:%S")
    thinking_message = f"## Thinking... ⏳\n\n**[{current_time}]** Generating your quiz. This may take a moment."

    # In the first yield, return the same thinking message for both outputs
    yield thinking_message, thinking_message

    # Input validation
    if not learning_objective.strip():
        error_message = "⚠️ **Error**: Please provide a learning objective."
        yield error_message, error_message
        return

    try:
        num_questions = int(num_questions)
        if num_questions < 1 or num_questions > 10:
            error_message = "⚠️ **Error**: Number of questions must be between 1 and 10."
            yield error_message, error_message
            return
    except ValueError:
        error_message = "⚠️ **Error**: Number of questions must be an integer."
        yield error_message, error_message
        return

    # Update thinking message to show progress
    current_time = datetime.now().strftime("%H:%M:%S")
    if enable_validation:
        thinking_message = f"## Thinking... ⏳\n\n**[{current_time}]** Generating questions and validating answers. This might take a bit longer."
    else:
        thinking_message = f"## Thinking... ⏳\n\n**[{current_time}]** Generating {num_questions} questions on: '{learning_objective}'"

    yield thinking_message, thinking_message

    # Prepare the payload with subject area and validation option
    payload = {
        "learning_objective": learning_objective,
        "num_questions": num_questions,
        "validate": enable_validation,
    }

    # Add subject area if provided
    if subject_area and subject_area != "General":
        # Prepend subject area to learning objective for better context
        payload["learning_objective"] = f"[{subject_area}] {learning_objective}"

    try:
        # Make the request to your Flask API
        response = requests.post(
            API_URL, json=payload, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        quiz_data = response.json()

        if "error" in quiz_data:
            error_message = f"⚠️ **Error from API**: {quiz_data['error']}"
            yield error_message, error_message
            return

        questions = quiz_data.get("questions", [])
        if not questions:
            error_message = "No questions were generated. Please try a different learning objective."
            yield error_message, error_message
            return

        # Store the quiz data for student mode
        quiz_state["current_quiz"] = quiz_data

        # Generate outputs for teacher and student views
        teacher_output = generate_teacher_view(learning_objective, questions)
        student_output = generate_student_view(learning_objective, questions)

        # Yield both outputs - teacher output first, student output second
        yield teacher_output, student_output

    except requests.exceptions.RequestException as e:
        error_message = f"⚠️ **Connection Error**: {str(e)}\n\nPlease check if the API server is running at {API_URL}."
        yield error_message, error_message
    except json.JSONDecodeError:
        error_message = f"⚠️ **Error**: Invalid response format from the API."
        yield error_message, error_message
    except Exception as e:
        error_message = f"⚠️ **Unexpected Error**: {str(e)}"
        yield error_message, error_message


def generate_teacher_view(learning_objective, questions):
    """Generate the teacher view of the quiz with all answers and explanations."""
    current_time = datetime.now().strftime("%H:%M:%S")
    output = f"## Generated Quiz: {learning_objective}\n\n"
    output += f"**Generated at:** {current_time} | **Questions:** {len(questions)}\n\n"

    # Add a print button for the quiz
    output += '<button onclick="window.print()" style="padding: 8px 16px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">Print Quiz</button>\n\n'

    for i, q in enumerate(questions, 1):
        # Basic question formatting
        question_output = (
            f"<details>\n"
            f"<summary><b>Question {i}: {q['question']}</b></summary>\n\n"
            f"**Options:**\n"
            f"- a) {q['options']['a']}\n"
            f"- b) {q['options']['b']}\n"
            f"- c) {q['options']['c']}\n"
            f"- d) {q['options']['d']}\n\n"
            f"**Correct Answer:** {q['correct_answer']}\n\n"
            f"**Explanation:** {q['explanation']}\n"
        )

        # Add validation results if present
        if "validation" in q:
            validation = q["validation"]
            validation_status = (
                "✅ Verified"
                if validation.get("is_correct") is True
                else (
                    "❌ Incorrect"
                    if validation.get("is_correct") is False
                    else "⚠️ Inconclusive"
                )
            )

            question_output += f"\n**Validation Status:** {validation_status}\n\n"
            question_output += f"**Validation Notes:** {validation['explanation']}\n\n"

            if validation.get("sources"):
                question_output += "**Sources:**\n"
                for source in validation["sources"]:
                    question_output += f"- [{source}]({source})\n"

        question_output += "</details>\n\n"
        output += question_output

    # Add a download button for the JSON data
    output += "---\n\n"
    output += "### Options\n\n"
    output += "<details>\n<summary>Download Quiz Data (JSON)</summary>\n\n"
    output += "```json\n"
    output += json.dumps(quiz_state["current_quiz"], indent=2)
    output += "\n```\n\nCopy the JSON above to save your quiz data.\n</details>\n\n"

    # Add a section for teacher notes
    output += "<details>\n<summary>Teacher Notes</summary>\n\n"
    output += "📝 Add your notes here for presenting this quiz to students.\n\n"
    output += "**Topics covered:**\n- " + learning_objective + "\n\n"
    output += (
        "**Preparation recommendations:**\n- Review the explanations for each answer\n"
    )
    output += "- Consider discussing common misconceptions related to these questions\n"
    output += "</details>\n\n"

    return output


def generate_student_view(learning_objective, questions):
    """Generate the student view of the quiz with questions and answer options only."""
    quiz_id = quiz_state["quiz_id"]
    current_time = datetime.now().strftime("%H:%M:%S")

    output = f"## Quiz: {learning_objective}\n\n"
    output += f"**Quiz ID:** {quiz_id} | **Questions:** {len(questions)}\n\n"
    output += "Select one answer for each question, then click 'Submit Quiz' to check your answers.\n\n"

    for i, q in enumerate(questions, 1):
        output += f"### Question {i}: {q['question']}\n\n"
        output += f"- **A)** {q['options']['a']}\n"
        output += f"- **B)** {q['options']['b']}\n"
        output += f"- **C)** {q['options']['c']}\n"
        output += f"- **D)** {q['options']['d']}\n\n"

    output += "---\n\n"
    output += "Once you've selected all your answers, click the 'Submit Quiz' button to see your results.\n"

    return output


def record_student_answer(question_num, answer):
    """Record a student's answer for a specific question."""
    if quiz_state["current_quiz"] is None:
        return "No active quiz. Please generate a quiz first."

    # Convert question_num to 0-based index for internal use
    idx = int(question_num) - 1

    # Validate question number
    if idx < 0 or idx >= len(quiz_state["current_quiz"]["questions"]):
        return f"⚠️ Invalid question number. Please enter a number between 1 and {len(quiz_state['current_quiz']['questions'])}."

    # Record answer (convert to lowercase for consistency)
    quiz_state["student_answers"][idx] = answer.lower()

    # Count how many questions have been answered
    total_questions = len(quiz_state["current_quiz"]["questions"])
    answered_count = len(quiz_state["student_answers"])

    return f"✅ Answer recorded for Question {question_num}. ({answered_count}/{total_questions} answered)"


def submit_student_quiz():
    """Process the student's answers and show results with score."""
    if quiz_state["current_quiz"] is None:
        return "No active quiz. Please generate a quiz first."

    questions = quiz_state["current_quiz"]["questions"]
    student_answers = quiz_state["student_answers"]

    # Calculate score
    correct_count = 0
    total_questions = len(questions)

    output = "## Quiz Results\n\n"

    # If not all questions are answered, provide a warning
    if len(student_answers) < total_questions:
        output += f"⚠️ **Warning:** You've only answered {len(student_answers)} out of {total_questions} questions.\n\n"

    # Calculate the score based on answered questions
    for idx, question in enumerate(questions):
        if idx in student_answers:
            student_answer = student_answers[idx]
            correct_answer = question["correct_answer"]

            is_correct = student_answer.lower() == correct_answer.lower()
            if is_correct:
                correct_count += 1

    # Calculate percentage score
    score_percentage = (correct_count / total_questions) * 100

    # Add score summary
    output += f"### Your Score: {correct_count}/{total_questions} ({score_percentage:.1f}%)\n\n"

    # Add a performance indicator
    if score_percentage >= 90:
        output += "🏆 **Excellent!** Outstanding performance!\n\n"
    elif score_percentage >= 80:
        output += "🎓 **Great job!** You've mastered most of the material.\n\n"
    elif score_percentage >= 70:
        output += "👍 **Good work!** You have a solid understanding.\n\n"
    elif score_percentage >= 60:
        output += "🔍 **Not bad.** Some areas need more focus.\n\n"
    else:
        output += "📚 **Keep studying.** This topic needs more review.\n\n"

    # Add detailed question review
    output += "### Question Review\n\n"

    for idx, question in enumerate(questions):
        q_num = idx + 1
        student_answer = student_answers.get(idx, "Not answered")
        correct_answer = question["correct_answer"]

        # Format the question result
        if idx in student_answers:
            is_correct = student_answers[idx].lower() == correct_answer.lower()
            status_icon = "✅" if is_correct else "❌"
        else:
            status_icon = "⚠️"

        output += f"<details>\n<summary>{status_icon} <b>Question {q_num}:</b> {question['question']}</summary>\n\n"

        # Display options with highlighting for correct/incorrect
        output += "**Options:**\n"

        for opt_key in ["a", "b", "c", "d"]:
            opt_text = question["options"][opt_key]
            prefix = ""

            # Add visual indicators for correct/student answers
            if opt_key == correct_answer:
                prefix = "✅ "  # Correct answer

            if idx in student_answers and opt_key == student_answers[idx].lower():
                if opt_key != correct_answer:
                    prefix = "❌ "  # Student's incorrect answer

            output += f"- **{opt_key.upper()})** {prefix}{opt_text}\n"

        # Show the student's answer
        output += f"\n**Your answer:** {student_answer.upper() if student_answer != 'Not answered' else student_answer}\n"
        output += f"**Correct answer:** {correct_answer.upper()}\n\n"

        # Add explanation
        output += f"**Explanation:** {question['explanation']}\n"
        output += "</details>\n\n"

    # Add a button to try again
    output += "---\n\n"
    output += "Want to improve your score? Review the explanations above and try again with a new quiz."

    return output


# Define common academic subject areas for the dropdown
SUBJECT_AREAS = [
    "General",
    "Biology",
    "Chemistry",
    "Physics",
    "Mathematics",
    "Computer Science",
    "History",
    "Literature",
    "Economics",
    "Psychology",
    "Philosophy",
    "Engineering",
    "Business",
    "Art & Design",
    "Medicine",
    "Law",
    "Environmental Science",
    "Sociology",
    "Political Science",
    "Linguistics",
]

# Define theme and layout
theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="green",
)

with gr.Blocks(title="Academic Quiz Generator", theme=theme) as demo:
    # State variables for quiz tracking
    current_mode = gr.State("teacher")

    # Header
    gr.Markdown("# 🎓 Academic Quiz Generator")

    # Mode selection tabs
    with gr.Tabs() as tabs:
        with gr.TabItem("👨‍🏫 Teacher Mode", id="teacher_tab") as teacher_tab:
            teacher_info = gr.Markdown(
                "Create and review quizzes with full answer keys and explanations."
            )

        with gr.TabItem("👨‍🎓 Student Mode", id="student_tab") as student_tab:
            student_info = gr.Markdown(
                "Take quizzes and test your knowledge without seeing the answers first."
            )

    # Quiz generation controls - shown in both modes
    with gr.Group():
        gr.Markdown("## Quiz Settings")

        with gr.Row():
            with gr.Column(scale=2):
                subject_area = gr.Dropdown(
                    choices=SUBJECT_AREAS,
                    label="Subject Area",
                    value="General",
                    info="Select a subject to provide better context (optional)",
                )

                learning_objective_input = gr.Textbox(
                    label="Learning Objective",
                    placeholder="e.g., Understand how natural selection drives evolution",
                    lines=3,
                    info="Be specific about what students should know or understand",
                )

            with gr.Column(scale=1):
                num_questions_input = gr.Slider(
                    label="Number of Questions",
                    value=3,
                    minimum=1,
                    maximum=10,
                    step=1,
                    info="More questions may take longer to generate",
                )

                validation_checkbox = gr.Checkbox(
                    label="Validate Answers",
                    value=False,
                    info="Check answer accuracy using web search (takes longer)",
                )

        with gr.Row():
            with gr.Column(scale=1):
                generate_button = gr.Button(
                    "✨ Generate Quiz", variant="primary", size="lg"
                )

            with gr.Column(scale=1):
                clear_button = gr.Button("🗑️ Clear", variant="secondary", size="lg")

    # Teacher view output
    with gr.Group(visible=True) as teacher_view:
        with gr.Accordion("📝 Quiz Output", open=True):
            teacher_output = gr.Markdown(
                value="Your quiz will appear here after generation."
            )

    # Student view components
    with gr.Group(visible=False) as student_view:
        # Quiz display
        with gr.Accordion("📝 Quiz Questions", open=True):
            student_output = gr.Markdown(
                value="Your quiz will appear here after generation."
            )

        # Answer input section
        with gr.Group():
            gr.Markdown("## Your Answers")
            with gr.Row():
                question_number = gr.Number(
                    label="Question Number",
                    minimum=1,
                    maximum=10,
                    value=1,
                    step=1,
                    precision=0,
                )
                answer_choice = gr.Radio(
                    choices=["A", "B", "C", "D"], label="Your Answer"
                )
                record_answer_button = gr.Button("Record Answer", variant="secondary")

            answer_status = gr.Markdown("Record your answers above.")

        # Submit quiz button
        submit_quiz_button = gr.Button("📋 Submit Quiz", variant="primary", size="lg")

        # Results display
        with gr.Accordion(
            "📊 Quiz Results", open=False, visible=False
        ) as results_accordion:
            results_output = gr.Markdown(
                value="Your results will appear here after submission."
            )

    # Function to handle tab changes
    def switch_to_teacher():
        return (
            "teacher",
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    def switch_to_student():
        return (
            "student",
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
        )

    # Set up tab switching logic
    teacher_tab.select(
        fn=switch_to_teacher,
        inputs=[],
        outputs=[current_mode, teacher_view, student_view, results_accordion],
    )

    student_tab.select(
        fn=switch_to_student,
        inputs=[],
        outputs=[current_mode, teacher_view, student_view, results_accordion],
    )

    # Event handlers for generation
    generate_button.click(
        fn=generate_quiz_stream,
        inputs=[
            learning_objective_input,
            num_questions_input,
            validation_checkbox,
            subject_area,
            current_mode,
        ],
        outputs=[teacher_output, student_output],
        queue=True,
    )

    # Clear all inputs and outputs
    def clear_all():
        return (
            "",
            3,
            False,
            "General",
            "Your quiz will appear here after generation.",
            "Your quiz will appear here after generation.",
            "Record your answers above.",
        )

    clear_button.click(
        fn=clear_all,
        inputs=None,
        outputs=[
            learning_objective_input,
            num_questions_input,
            validation_checkbox,
            subject_area,
            teacher_output,
            student_output,
            answer_status,
        ],
    )

    # Student mode answer recording
    record_answer_button.click(
        fn=record_student_answer,
        inputs=[question_number, answer_choice],
        outputs=[answer_status],
    )

    # Student mode quiz submission
    submit_quiz_button.click(
        fn=submit_student_quiz,
        inputs=[],
        outputs=[results_output],
    ).then(
        fn=lambda: gr.update(visible=True, open=True),
        inputs=None,
        outputs=[results_accordion],
    )

    # Example prompts
    with gr.Accordion("📚 Example Quiz Topics", open=False):
        gr.Examples(
            [
                [
                    "Biology",
                    "Explain how DNA replication occurs in eukaryotic cells",
                    3,
                    False,
                ],
                [
                    "Computer Science",
                    "Understand the principles of object-oriented programming",
                    5,
                    False,
                ],
                [
                    "Physics",
                    "Calculate the momentum and energy of a body in motion",
                    2,
                    False,
                ],
                [
                    "Psychology",
                    "Describe the major theories of personality development",
                    4,
                    False,
                ],
            ],
            inputs=[
                subject_area,
                learning_objective_input,
                num_questions_input,
                validation_checkbox,
            ],
            outputs=[teacher_output, student_output],
            fn=generate_quiz_stream,
            cache_examples=False,
        )

    # Tips section at the bottom
    gr.Markdown(
        "### 📚 Tips for Better Results\n"
        "- Be specific in your learning objectives\n"
        "- Use action verbs like 'Analyze', 'Evaluate', 'Compare', etc.\n"
        "- Specify the topic area for more relevant questions\n"
        "- Use validation for high-stakes or factual quizzes"
    )

# Launch the app
demo.launch(share=False)
