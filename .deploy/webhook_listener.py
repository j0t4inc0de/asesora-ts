import os
import hmac
import hashlib
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configuracion
PORT = 9000
# REEMPLAZA ESTO POR UN SECRETO SEGURO EN TU SERVIDOR (y usalo tambien en GitHub)
GITHUB_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET', 'mi-secreto-super-seguro')
DEPLOY_SCRIPT = '/home/jota-server/projects/asesora-ts/asesora-ts/.deploy/deploy.sh'

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Verificar la ruta
        if self.path != '/webhook':
            self.send_response(404)
            self.end_headers()
            return

        # 2. Obtener el cuerpo de la peticion
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # 3. Validar la firma de GitHub
        signature_header = self.headers.get('X-Hub-Signature-256')
        if not signature_header:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"No signature provided.")
            return

        # Calcular nuestra propia firma
        hash_object = hmac.new(GITHUB_SECRET.encode('utf-8'), msg=post_data, digestmod=hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()

        if not hmac.compare_digest(expected_signature, signature_header):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature.")
            return

        # 4. Procesar el evento
        event = self.headers.get('X-GitHub-Event')
        if event == 'push':
            print("Recibido evento PUSH. Ejecutando script de despliegue...")
            # Devolver OK a GitHub rapidamente para no mantener la conexion colgada
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Despliegue iniciado.")
            
            # Ejecutar el script en segundo plano
            try:
                # Asegurar que el script tenga permisos de ejecucion
                os.chmod(DEPLOY_SCRIPT, 0o755)
                subprocess.Popen([DEPLOY_SCRIPT])
                print("Script ejecutado correctamente en segundo plano.")
            except Exception as e:
                print(f"Error ejecutando script: {e}")
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Ignorando evento (no es push).")

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, WebhookHandler)
    print(f"Servidor Webhook escuchando en el puerto {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print("Servidor detenido.")

if __name__ == '__main__':
    run_server()
