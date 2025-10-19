# Web Application Exercise

A little exercise to build a web application following an agile development process. See the [instructions](instructions.md) for more detail.

## Product vision statement

A simple web app to help students organize, prioritize, and keep track of their homework and tasks efficiently.

## User stories

[Issues Page](https://github.com/swe-students-fall2025/2-web-app-spogs/issues)

## Steps necessary to run the software

### Prerequisites

Before you begin, ensure you have the following installed on your machine:

- **Python 3.8 or higher**: [Download Python](https://www.python.org/downloads/)
- **pip**: Python's package installer (comes with Python)

### 1. Install pipenv

If you don't have pipenv installed, install it using pip:

```bash
pip install pipenv
```

### 2. Clone the repository

Clone this repository to your local machine:

```bash
git clone https://github.com/swe-students-fall2025/2-web-app-spogs.git
cd 2-web-app-spogs
```

### 3. Configure environment variables

1. Copy the example environment file:

```bash
cp env.example .env
```

2. Open `.env` in a text editor and fill in your configuration:

```
MONGO_URI=your-mongo-uri-here
MONGO_USER=your-mongo-username-here
MONGO_PASS=your-mongo-password-here
PORT=10000
SECRET_KEY=your-secret-key-here
```

**Configuration details:**

- `MONGO_URI`: Provided MongoDB Atlas connection string
- `MONGO_USER`: Provided MongoDB username
- `MONGO_PASS`: Provided MongoDB password
- `PORT`: Desired port number for the web server (default: 10000)
- `SECRET_KEY`: A random secret key for Flask sessions (generate a secure random string) – will be used for authentication

### 4. Activate the virtual environment

Enter the pipenv shell:

```bash
pipenv shell
```

You should see your terminal prompt change to indicate you're in the virtual environment.

### 5. Install dependencies

Install all required Python packages using pipenv:

```bash
pipenv install
```

This will create a virtual environment and install all dependencies listed in `Pipfile.lock`.


### 6. Run the application

Start the Flask development server:

```bash
pipenv run python3 app.py
```

You should see output indicating the server is running:

```
* Running on http://127.0.0.1:10000
```

### 7. Access the application

Open your web browser and navigate to:

```
http://localhost:10000
```


### 8. Stopping the application

To stop the server, press `Ctrl+C` in the terminal.

To exit the pipenv shell:

```bash
exit
```

## Task boards

[spogs - Project 2 Sprint 1](https://github.com/orgs/swe-students-fall2025/projects/17)
[spogs – Project 2 Sprint 2](https://github.com/orgs/swe-students-fall2025/projects/48)