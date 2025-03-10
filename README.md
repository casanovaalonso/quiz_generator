# Quiz Generator

A system for generating educational multiple-choice quizzes based on learning objectives, designed for higher education use cases.

## Overview

The Quiz Generator is an AI-powered application that creates high-quality, university-level multiple-choice questions based on specific learning objectives. It leverages OpenAI's GPT models to generate contextually relevant questions, with optional fact verification through web search.

### Key Features

- **Custom Quiz Generation**: Create quizzes based on specific learning objectives
- **Answer Validation**: Verify correct answers using web search (optional)
- **Multiple Interfaces**: Access via API, UI, or programmatically
- **Teacher and Student Modes**: Different views for creating and taking quizzes

## Code Structure

The project follows a modular architecture with clear separation of concerns:

```
quiz-generator/
├── quiz_generator/            # Main package
│   ├── __init__.py            # Package initialization
│   ├── app.py                 # Flask API entry point
│   ├── generator.py           # Quiz generation logic
│   ├── validator.py           # Answer validation service
│   ├── gradio_ui.py           # Gradio-based web interface
│   ├── models/                # Data models
│   │   ├── __init__.py
│   │   └── quiz.py            # Pydantic models for quiz data
│   └── notebooks/             # Development notebooks
│       └── prototype.ipynb    # Prototyping and testing
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── test_api/              # API tests
│   └── test_services/         # Service tests
├── pyproject.toml             # Project configuration and dependencies
└── README.md                  # This file
```

### Core Components

1. **Models** (`models/quiz.py`): Defines the data structures for quiz questions and validation results using Pydantic.

2. **Generator** (`generator.py`): Handles the creation of quiz questions by interfacing with the OpenAI API.

3. **Validator** (`validator.py`): Uses search capabilities to validate the factual accuracy of answers.

4. **API** (`app.py`): Provides a Flask-based RESTful API for interacting with the generation service.

5. **UI** (`gradio_ui.py`): Offers a user-friendly web interface built with Gradio for creating and taking quizzes.

## Installation & Setup

### Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- OpenAI API key

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/quiz-generator.git
cd quiz-generator
```

### Step 2: Install Dependencies

```bash
# Using Poetry (recommended)
poetry install

# Using pip
pip install -e .
```

### Step 3: Set Up Environment Variables

Create a `.env` file in the root directory:

```
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
PORT=5000
DEBUG_MODE=True
DEFAULT_NUM_QUESTIONS=3
MAX_NUM_QUESTIONS=10
ALLOWED_ORIGINS=*
```

## Running the Application

### Running the API Server

```bash
# Using Poetry
poetry run python -m quiz_generator.app
```

The API will be available at `http://localhost:5000`.

### Running the UI

```bash
# Using Poetry
poetry run python -m quiz_generator.gradio_ui
```

The web interface will be available at `http://localhost:7860`.

## API Usage

### Generate a Quiz

**Endpoint**: `POST /generate-quiz`

**Request Body**:
```json
{
  "learning_objective": "Balance chemical equations using the law of conservation of mass",
  "num_questions": 3,
  "validate": false
}
```

**Response**:
```json
{
  "questions": [
    {
      "question": "Which of the following correctly balances the chemical equation for the combustion of methane (CH4)?",
      "options": {
        "a": "CH4 + 2O2 → CO2 + 2H2O",
        "b": "CH4 + O2 → CO2 + H2O",
        "c": "2CH4 + 3O2 → 2CO2 + 4H2O",
        "d": "CH4 + O2 → 2CO2 + 2H2O"
      },
      "correct_answer": "a",
      "explanation": "The correct balanced equation shows that one molecule of methane reacts with two molecules of oxygen to produce one molecule of carbon dioxide and two molecules of water, in line with the law of conservation of mass."
    },
    // Additional questions...
  ]
}
```

## Testing

Run the test suite using pytest:

```bash
# Using Poetry
poetry run pytest
```

## Future Improvements

### 1. Enhanced Model Selection

Currently, the application uses `gpt-4o-mini` as the default model. Potential improvements include:

- **Model Configuration UI**: Allow users to select different OpenAI models based on their needs
- **Model Caching**: Implement caching for similar queries to reduce API costs
- **Local Model Integration**: Add support for open-source models like Llama, Mistral, or Falcon

### 2. Dockerization

Containerizing the application would improve deployment consistency:

```dockerfile
# Example Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY poetry.lock pyproject.toml ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

COPY . .

EXPOSE 5000
EXPOSE 7860

CMD ["python", "-m", "quiz_generator.app"]
```

Docker Compose could be used to run both the API and UI services:

```yaml
# docker-compose.yml
version: '3'
services:
  api:
    build: .
    ports:
      - "5000:5000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    command: python -m quiz_generator.app
  
  ui:
    build: .
    ports:
      - "7860:7860"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    command: python -m quiz_generator.gradio_ui
```