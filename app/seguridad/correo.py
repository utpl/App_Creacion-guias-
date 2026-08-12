"""Envio de correo. En desarrollo escribe a disco en vez de enviar."""

from datetime import datetime, timezone
from pathlib import Path

from app.configuracion import configuracion

CARPETA_DESARROLLO = Path("correos_dev")


def enviar(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Envia un correo. En desarrollo lo guarda como archivo."""
    if configuracion.entorno == "desarrollo":
        CARPETA_DESARROLLO.mkdir(exist_ok=True)
        marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archivo = CARPETA_DESARROLLO / f"{marca}-{destinatario}.txt"
        archivo.write_text(
            f"Para: {destinatario}\nAsunto: {asunto}\n\n{cuerpo}\n",
            encoding="utf-8",
        )
        print(f"[correo guardado] {archivo}")
        return

    # En produccion se encolara en RQ y saldra por SES.
    raise NotImplementedError(
        "El envio real de correo se configura al desplegar."
    )


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
