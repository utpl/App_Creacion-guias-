"""Envio de correo por SMTP, encolado en segundo plano."""

import smtplib
from email.message import EmailMessage

from app.configuracion import configuracion


def _enviar_ahora(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Envio sincrono. Lo ejecuta el worker, nunca la peticion HTTP."""
    mensaje = EmailMessage()
    mensaje["From"] = (
        f"{configuracion.remitente_nombre} <{configuracion.remitente_correo}>"
    )
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)

    with smtplib.SMTP(configuracion.smtp_host, configuracion.smtp_puerto,
                      timeout=15) as servidor:
        if configuracion.smtp_tls:
            servidor.starttls()
        if configuracion.smtp_usuario and configuracion.smtp_password:
            servidor.login(
                configuracion.smtp_usuario,
                configuracion.smtp_password.get_secret_value(),
            )
        servidor.send_message(mensaje)


def enviar(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Encola el envio. Si la cola falla, envia directo para no perderlo."""
    try:
        from redis import Redis
        from rq import Queue

        cola = Queue("correo", connection=Redis.from_url(
            str(configuracion.url_redis)
        ))
        cola.enqueue(_enviar_ahora, destinatario, asunto, cuerpo)
    except Exception:
        _enviar_ahora(destinatario, asunto, cuerpo)


def enlace_recuperacion(url: str, nombre: str) -> tuple[str, str]:
    asunto = "Restablecer su contraseña · App-EdiLoja"
    cuerpo = (
        f"Hola {nombre},\n\n"
        f"Recibimos una solicitud para restablecer su contraseña.\n\n"
        f"{url}\n\n"
        f"El enlace caduca en {configuracion.minutos_token_recuperacion} minutos "
        f"y solo puede usarse una vez.\n\n"
        f"Si no fue usted, ignore este mensaje. Su contraseña no ha cambiado."
    )
    return asunto, cuerpo


def aviso_cambio(nombre: str) -> tuple[str, str]:
    asunto = "Su contraseña fue modificada · App-EdiLoja"
    cuerpo = (
        f"Hola {nombre},\n\n"
        f"La contraseña de su cuenta acaba de cambiar y todas las sesiones "
        f"abiertas se cerraron.\n\n"
        f"Si no fue usted, comuníquese de inmediato con soporte."
    )
    return asunto, cuerpo
