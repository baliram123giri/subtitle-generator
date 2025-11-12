pipeline {
    // Run the pipeline on any available Jenkins agent
    agent any

    triggers {
        githubPush()
    }

    // Environment variables for the pipeline
    environment {
        // Your Docker Hub username.
        DOCKER_USERNAME      = "baliram123giri"
        // The name of the Docker image.
        IMAGE_NAME           = "${env.DOCKER_USERNAME}/flask-video-app"
        // Credentials will be pulled from Jenkins Credentials manager
        MODAL_TOKEN_ID       = credentials('modal-token-id')
        MODAL_TOKEN_SECRET   = credentials('modal-token-secret')
        DOCKER_CREDENTIALS   = credentials('docker-hub-credentials')
        // Jenkins credential ID for SSH access to your server
        SERVER_SSH_CREDS     = 'server-ssh-credentials' 
    }

    stages {
        // Stage 1: Checkout code from the repository
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }

        // Stage 2: Deploy the serverless worker to Modal
        stage('Deploy to Modal') {
            steps {
                echo "Deploying worker to Modal..."
                sh '''
                python3 -m venv .venv
                .venv/bin/pip install modal
                .venv/bin/modal deploy modal_worker.py
                '''
            }
        }

        // Stage 3: Build the Docker image for the application
        stage('Build Docker Image') {
            steps {
                echo "Building Docker image: ${IMAGE_NAME}:${env.BUILD_ID}"
                sh "docker build -t ${IMAGE_NAME}:${env.BUILD_ID} ."
                sh "docker tag ${IMAGE_NAME}:${env.BUILD_ID} ${IMAGE_NAME}:latest"
            }
        }

        // Stage 4: Push the Docker image to a container registry (Docker Hub)
        stage('Push Docker Image') {
            steps {
                echo "Pushing Docker image to Docker Hub..."
                // Use the Docker Hub credentials stored in Jenkins
                withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', passwordVariable: 'DOCKER_PASSWORD', usernameVariable: 'DOCKER_USERNAME')]) {
                    sh "docker login -u ${DOCKER_USERNAME} -p ${DOCKER_PASSWORD}"
                    sh "docker push ${IMAGE_NAME}:${env.BUILD_ID}"
                    sh "docker push ${IMAGE_NAME}:latest"
                }
            }
        }

        // Stage 5: Deploy the new container to the production server
        stage('Deploy to Server') {
            steps {
                echo "Deploying container to server 38.242.147.19..."
                // Use sshagent to securely connect to your server
                sshagent (credentials: [SERVER_SSH_CREDS]) {
                    // Replace 'user@38.242.147.19' with your actual username on the server
                    sh '''
                        ssh -o StrictHostKeyChecking=no root@38.242.147.19 <<'EOF'
                        # Pull the latest image from Docker Hub
                        docker pull ${IMAGE_NAME}:latest
                        
                        # Stop and remove the old container if it exists
                        if [ \$(docker ps -q -f name=flask-app) ]; then
                            docker stop flask-app
                            docker rm flask-app
                        fi
                        
                        # Run the new container
                        docker run -d \
                            --name flask-app \
                            -p 3300:3300 \
                            --restart always \
                            -e MODAL_TOKEN_ID=${MODAL_TOKEN_ID} \
                            -e MODAL_TOKEN_SECRET=${MODAL_TOKEN_SECRET} \
                            -e IMAGEKIT_PRIVATE_KEY=${env.IMAGEKIT_PRIVATE_KEY} \
                            -e IMAGEKIT_PUBLIC_KEY=${env.IMAGEKIT_PUBLIC_KEY} \
                            -e IMAGEKIT_URL_ENDPOINT=${env.IMAGEKIT_URL_ENDPOINT} \
                            ${IMAGE_NAME}:latest
                        EOF
                    '''
                }
            }
        }
    }

    post {
        always {
            echo 'Pipeline finished. Cleaning up workspace.'
            // Clean up the local Docker image to save space on the Jenkins agent
            sh "docker rmi ${IMAGE_NAME}:${env.BUILD_ID} || true"
            sh 'rm -rf .venv'
        }
    }
}
