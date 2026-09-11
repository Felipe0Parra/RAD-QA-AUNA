# Guia de comandos de terminal en linux para verificar la seguridad del repositorio usando (Socket, Gitleaks y Bandit)

rm -r /etc/apt/sources.list.d/nodesource.list
rm -r /etc/apt/keyrings/nodesource.gpg
sudo apt-get install -y curl
curl -fsSL https://deb.nodesource.com/setup_26.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v
sudo npm install -g npm@12.0.2
sudo socket npm install

sudo apt install gitleaks
sudo snap install bandit


Empezemos por:

- Comandos de guia para identificar las opciones disponibles y la sintaxis de cada herramienta:

socket --help
gitleaks help
bandit --help

- Normalmente usados para el analisis:

socket scan (Hace el barrido y abre el informe del analisis en un html).
gitleaks detect (Nos da el resultado en terminal del barrido y la cantidad de secretos detectados).
bandit -r . -x ./.venv (Nos da el reporte completo de las fallas en ciberseguridad de la estrucura del codigo).
