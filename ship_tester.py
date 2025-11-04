import asyncio
import websockets
import ssl
import logging
from websockets import Subprotocol

# --- Configuration ---
# Replace with the IP address or hostname of your EEBus peer (Device B)
PEER_HOSTNAME = "192.168.178.150"
PEER_PORT = 4712

# Full debug logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("websockets").setLevel(logging.DEBUG)


async def test_ship_cmi():
    """
    Connects to a SHIP peer, performs the WebSocket handshake, and completes the CMI.
    """
    uri = f"wss://{PEER_HOSTNAME}:{PEER_PORT}/ship/"

    # SHIP requires TLS, but for local testing, we often use self-signed certificates and dont verify certs
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        logging.info("--- Initiating WebSocket Connection ---")
        async with websockets.connect( # handshake happens here
                uri,
                ssl=ssl_context,
                subprotocols=["ship"]
        ) as websocket:

            logging.info("--- WebSocket Handshake Successful ---")
            logging.info(f"Connected to: {websocket.remote_address}")
            logging.info(f"Subprotocol negotiated: {websocket.subprotocol}")
            #logging.info(f"Response headers:\n{websocket.response_headers}")
            logging.info("-" * 40)

            # --- CMI (Connection Mode Initialization) ---

            # Step 1: Client sends CMI message with value 0
            # A SHIP CMI message is composed of a MessageType byte and a MessageValue.
            # MessageType 'init' is 0x00. The MessageValue for the first step is also 0.
            cmi_client_msg = bytes([0x00, 0x00])
            logging.info(f"--> Sending CMI Client Message (State: CMI_STATE_CLIENT_SEND): {cmi_client_msg.hex()}")
            await websocket.send(cmi_client_msg)

            # Step 2: Client waits for the server's CMI response
            logging.info("<-- Awaiting CMI Server Response (State: CMI_STATE_CLIENT_WAIT)")
            cmi_server_response = await websocket.recv()

            logging.info(f"<-- Received CMI Server Response: {cmi_server_response.hex()}")

            # Step 3: Client evaluates the server's response
            if isinstance(cmi_server_response, bytes) and len(cmi_server_response) >= 2:
                msg_type = cmi_server_response[0]
                cmi_head = cmi_server_response[1]

                logging.info(f"    - MessageType: {hex(msg_type)}")
                logging.info(f"    - CmiHead: {cmi_head}")

                if msg_type == 0x00 and cmi_head == 0:
                    logging.info("--- CMI Handshake Successful ---")
                    logging.info("Entering state 'Connection data preparation'.")
                else:
                    logging.error("CMI Handshake FAILED: Server sent an invalid response.")
                    await websocket.close()
                    return
            else:
                logging.error(f"CMI Handshake FAILED: Received unexpected data type: {type(cmi_server_response)}")
                await websocket.close()
                return

            # The connection is now ready for the next SHIP state (Connection state Hello)
            logging.info("Test finished. Closing connection.")
            await websocket.close()

    except websockets.exceptions.InvalidHandshake as e:
        logging.error("--- WebSocket Handshake FAILED ---")
        logging.error(f"The server rejected the connection. Status: {e.status_code}")
        logging.error(
            "This often happens if the 'Sec-WebSocket-Protocol: ship' header was not accepted or returned by the server.")
        logging.error(f"Server response headers:\n{e.headers}")
    except ConnectionRefusedError:
        logging.error(f"Connection to {PEER_HOSTNAME}:{PEER_PORT} was refused. Is the peer running and reachable?")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(test_ship_cmi())