pipeline {
    agent {
        docker { image 'alpine:3.7' }
    }
    stages {
        stage('Build') {
            steps {
                echo "Running ${env.BUILD_ID} on ${env.JENKINS_URL}"
                echo "Branch: ${env.BRANCH_NAME}"
                sh 'cat /etc/alpine-release'
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
