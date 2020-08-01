pipeline {
    environment {
        PYTHONDONTWRITEBYTECODE = 1
        PYTHONUNBUFFERED = 1
	 }
    agent none
    stages {
        stage('Initialization') {
            agent any
            steps {
                checkout scm
            }
        }
        stage('Linting') {
            agent { 
                docker {
                    image 'python:3'
                }
            }
            steps {
                echo "Branch: ${env.BRANCH_NAME}"
                sh "pip install --upgrade --no-cache-dir black"
                sh "/usr/local/bin/black --check --diff ."
            }
        }
        stage('Test') {
            steps {
                echo 'Testing..'
            }
        }
        stage('Deploy') {
            steps {
                echo 'Deploying....'
            }
        }
    }
}
