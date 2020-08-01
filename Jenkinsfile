pipeline {
    agent none
    stages {
        stage('Initialization') {
            agent any
            steps {
                checkout scm
            }
        }
        stage('Build') {
            agent { 
                docker {
                    image 'alpine:3.12.0'
                    args '-u root'
                }
            }
            steps {
                echo "Branch: ${env.BRANCH_NAME}"
                sh "apk update"
                sh "apk add python3 py3-pip build-base python3-dev"
                sh "pip install black"
                sh "black ."
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
