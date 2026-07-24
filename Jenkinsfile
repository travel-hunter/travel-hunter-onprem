pipeline {
    agent { label 'deploy' }

    environment {
        PROJECT_DIR = "/home/deploy/travel-hunter-onprem"
        BRANCH_NAME = "develop"
        ENV_FILE = "deploy/.env.prod"
        COMPOSE_FILE = "compose.tunnel.yaml"
    }

    stages {
        stage('Check Environment') {
            steps {
                sh '''
                    echo "===== 실행 위치 확인 ====="
                    whoami
                    hostname
                    pwd

                    echo "===== 도구 확인 ====="
                    git --version
                    docker --version
                    docker compose version

                    echo "===== 프로젝트 확인 ====="
                    cd ${PROJECT_DIR}
                    pwd
                    ls -al

                    echo "===== Git 상태 ====="
                    git status
                '''
            }
        }

        stage('Pull Latest Code') {
            steps {
                sh '''
                    echo "===== 최신 코드 가져오기 ====="
                    cd ${PROJECT_DIR}

                    git config --global --add safe.directory ${PROJECT_DIR}
                    git fetch origin
                    git checkout ${BRANCH_NAME}
                    git pull origin ${BRANCH_NAME}
                '''
            }
        }

        stage('Build and Deploy') {
            steps {
                sh '''
                    echo "===== Docker Compose 빌드 및 배포 ====="
                    cd ${PROJECT_DIR}

                    docker compose \
                      --env-file ${ENV_FILE} \
                      -f ${COMPOSE_FILE} \
                      up -d --build
                '''
            }
        }

        stage('Run DB Migration') {
            steps {
                sh '''
                    echo "===== DB Migration 실행 ====="
                    cd ${PROJECT_DIR}

                    docker compose \
                      --env-file ${ENV_FILE} \
                      -f ${COMPOSE_FILE} \
                      exec -T backend python -m alembic upgrade head
                '''
            }
        }

        stage('Check Containers') {
            steps {
                sh '''
                    echo "===== 컨테이너 상태 확인 ====="
                    cd ${PROJECT_DIR}

                    docker compose \
                      --env-file ${ENV_FILE} \
                      -f ${COMPOSE_FILE} \
                      ps
                '''
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                    echo "===== 내부 Caddy 테스트 ====="
                    cd ${PROJECT_DIR}

                    docker run --rm --network travel-hunter-onprem_default curlimages/curl:latest \
                      -I -H "Host: dev.travel-hunter.co.kr" http://caddy:80

                    echo "===== 외부 도메인 테스트 ====="
                    curl -I https://dev.travel-hunter.co.kr || true
                '''
            }
        }
    }

    post {
        success {
            echo "배포 성공"
        }

        failure {
            echo "배포 실패. Jenkins Console Output 확인 필요"
        }
    }
}
