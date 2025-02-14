import pytest
import socket
import time
import threading
import subprocess
from typing import List, Tuple

class TestChatSystem:
    @pytest.fixture(scope="session")
    def system_setup(self):
        # Start load balancer
        lb_process = subprocess.Popen(["./loadbalancer"], 
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE)
        
        # Configure load balancer with 3 servers starting at port 8000
        lb_process.stdin.write(b"8000\n3\n")
        lb_process.stdin.flush()
        
        # Start 3 servers
        server_processes = []
        for port in range(8000, 8003):
            server_process = subprocess.Popen(["./server", str(port)])
            server_processes.append(server_process)
        
        # Wait for system startup
        time.sleep(2)
        
        yield lb_process, server_processes
        
        # Cleanup
        lb_process.terminate()
        for server in server_processes:
            server.terminate()

    def test_client_connection(self, system_setup):
        """Test basic client connection to load balancer"""
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("localhost", 6000))
        
        # Send client name and room
        client.send(b"TestClient")
        client.send(b"Room1")
        
        # Receive server port
        server_port = int.from_bytes(client.recv(4), byteorder='big')
        assert 8000 <= server_port <= 8002
        
        client.close()

    def test_room_allocation(self, system_setup):
        """Test that clients requesting same room get same server"""
        def connect_client(name: str, room: str) -> int:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("localhost", 6000))
            client.send(name.encode())
            client.send(room.encode())
            port = int.from_bytes(client.recv(4), byteorder='big')
            client.close()
            return port
            
        port1 = connect_client("Client1", "SameRoom")
        port2 = connect_client("Client2", "SameRoom")
        
        assert port1 == port2

    def test_load_distribution(self, system_setup):
        """Test load balancer distributes clients across servers"""
        ports = []
        for i in range(5):
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("localhost", 6000))
            client.send(f"Client{i}".encode())
            client.send(f"Room{i}".encode())
            port = int.from_bytes(client.recv(4), byteorder='big')
            ports.append(port)
            client.close()
            
        # Verify distribution across servers
        assert len(set(ports)) > 1

    def test_server_failure_recovery(self, system_setup):
        """Test system handles server failure"""
        lb_process, server_processes = system_setup
        
        # Get initial server assignment
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("localhost", 6000))
        client.send(b"Client1")
        client.send(b"Room1")
        initial_port = int.from_bytes(client.recv(4), byteorder='big')
        client.close()
        
        # Kill server process for that port
        server_idx = initial_port - 8000
        server_processes[server_idx].terminate()
        time.sleep(HEARTBEAT_INTERVAL + 1)
        
        # Try connecting again
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("localhost", 6000))
        client.send(b"Client2")
        client.send(b"Room2")
        new_port = int.from_bytes(client.recv(4), byteorder='big')
        client.close()
        
        assert new_port != initial_port

    def test_chat_functionality(self, system_setup):
        """Test actual chat functionality between clients"""
        def client_chat(name: str, room: str, messages: List[str]) -> List[str]:
            received_msgs = []
            
            # Connect to load balancer
            lb_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            lb_client.connect(("localhost", 6000))
            lb_client.send(name.encode())
            lb_client.send(room.encode())
            
            # Get server port and connect
            server_port = int.from_bytes(lb_client.recv(4), byteorder='big')
            lb_client.close()
            
            chat_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            chat_client.connect(("localhost", server_port))
            
            # Send messages
            for msg in messages:
                chat_client.send(msg.encode())
                response = chat_client.recv(1024).decode()
                received_msgs.append(response)
            
            chat_client.close()
            return received_msgs
            
        # Test chat between two clients
        client1_msgs = ["Hello!", "How are you?"]
        client2_msgs = ["Hi!", "I'm good!"]
        
        thread1 = threading.Thread(target=client_chat, 
                                 args=("Client1", "ChatRoom", client1_msgs))
        thread2 = threading.Thread(target=client_chat, 
                                 args=("Client2", "ChatRoom", client2_msgs))
        
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

if __name__ == "__main__":
    pytest.main(["-v"])
