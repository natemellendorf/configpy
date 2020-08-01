pipeline {
    agent none
    stages {
        stage('Build') {
            agent { 
                docker 'alpine:3.7' 
                args '-u root'
            }
            steps {
                echo "Branch: ${env.BRANCH_NAME}"
                checkout scm
                sh "apk add python3"
                sh "apk add py3-pip"
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
