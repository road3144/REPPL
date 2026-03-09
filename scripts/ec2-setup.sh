#!/bin/bash
# EC2 초기 설정 스크립트 (Ubuntu 22.04 기준)
# 사용법: ssh -i J14A401T.pem ubuntu@<EC2_IP> "bash -s" < scripts/ec2-setup.sh

set -e

echo "=== Docker 설치 ==="
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "=== ubuntu 유저를 docker 그룹에 추가 ==="
sudo usermod -aG docker ubuntu

echo "=== Docker 서비스 시작 ==="
sudo systemctl enable docker
sudo systemctl start docker

echo "=== 앱 디렉터리 생성 ==="
mkdir -p ~/app/nginx

echo "=== 방화벽 설정 (ufw) ==="
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (nginx)
sudo ufw allow 29092/tcp # Kafka (GPU 서버 접근용)
# sudo ufw enable  # 주석 해제하여 방화벽 활성화

echo ""
echo "=== 설치 완료 ==="
echo "재로그인 후 'docker ps' 명령으로 정상 동작을 확인하세요."
echo "EC2 보안 그룹에서도 80, 29092 포트를 열어주세요."