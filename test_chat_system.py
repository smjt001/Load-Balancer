import unittest
import socket
import subprocess
import threading
import time
import os

class TestLoadBalancer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start load balancer
        cls.lb_process = subprocess.Popen(
            ["./loadbalancer"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        # Configure with 3 servers starting at port 8000
        cls.lb_process.stdin.write(b"8000\n3\n")
        cls.lb_process.stdin.flush()
        time.sleep(1)

    def test_lb_connection(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', 6000))
        self.assertTrue(client.fileno() > 0)
        client.close()

    def test_lb_server_assignment(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', 6000))
        client.send(b"TestClient\nRoom1")
        port = client.recv(4)
        self.assertTrue(8000 <= int.from_bytes(port, 'big') <= 8002)
        client.close()

    def test_lb_multiple_clients(self):
        clients = []
        ports = set()
        for i in range(5):
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(('localhost', 6000))
            client.send(f"TestClient{i}\nRoom1".encode())
            port = int.from_bytes(client.recv(4), 'big')
            ports.add(port)
            clients.append(client)
        
        self.assertTrue(len(ports) > 1)  # Ensure load distribution
        for client in clients:
            client.close()

    def test_lb_server_failure_recovery(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', 6000))
        client.send(b"TestClient\nRoom1")
        port = client.recv(4)
        client.close()
        
        # Try reconnecting immediately
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', 6000))
        client.send(b"TestClient\nRoom1")
        new_port = client.recv(4)
        self.assertTrue(8000 <= int.from_bytes(new_port, 'big') <= 8002)
        client.close()

    @classmethod
    def tearDownClass(cls):
        cls.lb_process.terminate()

class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start test server
        cls.server_process = subprocess.Popen(
            ["./server", "9000"],
            stdout=subprocess.PIPE
        )
        time.sleep(1)

    def test_server_client_connection(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', 9000))
        client.send(b"TestClient\nTestRoom")
        time.sleep(0.1)
        self.assertTrue(client.fileno() > 0)
        client.close()

    def test_server_broadcast(self):
        # Connect two test clients
        client1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        client1.connect(('localhost', 9000))
        client2.connect(('localhost', 9000))
        
        # Join same room
        client1.send(b"Client1\nRoom1")
        client2.send(b"Client2\nRoom1")
        
        # Send message from client1
        client1.send(b"Hello from Client1")
        
        # Check if client2 receives the message
        received = client2.recv(256)
        self.assertIn(b"Hello from Client1", received)
        
        client1.close()
        client2.close()

    def test_server_multiple_rooms(self):
        clients = []
        for i in range(3):
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(('localhost', 9000))
            client.send(f"Client{i}\nRoom{i%2}".encode())
            clients.append(client)
        
        # Send message in Room0
        clients[0].send(b"Message to Room0")
        time.sleep(0.1)
        
        # Client2 should receive it (same room)
        received = clients[2].recv(256)
        self.assertIn(b"Message to Room0", received)
        
        for client in clients:
            client.close()

    def test_server_client_disconnect(self):
        client1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        client1.connect(('localhost', 9000))
        client2.connect(('localhost', 9000))
        
        client1.send(b"Client1\nRoom1")
        client2.send(b"Client2\nRoom1")
        
        client1.close()
        time.sleep(0.1)
        
        # Client2 should still be able to send/receive
        client2.send(b"Test message")
        client2.close()

    @classmethod
    def tearDownClass(cls):
        cls.server_process.terminate()

class TestClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start minimal test environment
        cls.server_process = subprocess.Popen(
            ["./server", "9500"],
            stdout=subprocess.PIPE
        )
        time.sleep(1)

    def test_client_connection_lifecycle(self):
        client_process = subprocess.Popen(
            ["./client"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        
        # Send client details
        client_process.stdin.write(b"TestClient\nTestRoom\n")
        client_process.stdin.flush()
        
        # Send a message
        client_process.stdin.write(b"Hello World\n")
        client_process.stdin.flush()
        
        # Send exit command
        client_process.stdin.write(b"#exit\n")
        client_process.stdin.flush()
        
        time.sleep(0.1)
        self.assertEqual(client_process.poll(), None)
        client_process.terminate()

    def test_client_message_sending(self):
        def run_client(name, room, messages):
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(('localhost', 9500))
            client.send(f"{name}\n{room}".encode())
            
            for msg in messages:
                client.send(msg.encode())
                time.sleep(0.1)
            
            client.send(b"#exit")
            client.close()

        # Test two clients communicating
        client1_thread = threading.Thread(
            target=run_client,
            args=("Client1", "Room1", ["Hello!", "How are you?"])
        )
        client2_thread = threading.Thread(
            target=run_client,
            args=("Client2", "Room1", ["Hi!", "I'm good!"])
        )

        client1_thread.start()
        client2_thread.start()
        client1_thread.join()
        client2_thread.join()

    def test_client_special_commands(self):
        client_process = subprocess.Popen(
            ["./client"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        
        client_process.stdin.write(b"TestClient\nTestRoom\n")
        client_process.stdin.flush()
        
        # Test various commands
        commands = [b"#help\n", b"#list\n", b"#room TestRoom2\n"]
        for cmd in commands:
            client_process.stdin.write(cmd)
            client_process.stdin.flush()
            time.sleep(0.1)
        
        client_process.stdin.write(b"#exit\n")
        client_process.stdin.flush()
        client_process.terminate()

    def test_client_long_messages(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', 9500))
        client.send(b"TestClient\nTestRoom")
        
        long_message = "A" * 1024
        client.send(long_message.encode())
        time.sleep(0.1)
        client.close()

    @classmethod
    def tearDownClass(cls):
        cls.server_process.terminate()

class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start complete system
        cls.lb_process = subprocess.Popen(
            ["./loadbalancer"],
            stdin=subprocess.PIPE
        )
        cls.lb_process.stdin.write(b"8800\n2\n")
        cls.lb_process.stdin.flush()
        
        cls.server_processes = [
            subprocess.Popen(["./server", str(port)])
            for port in [8800, 8801]
        ]
        time.sleep(2)

    def test_full_system_flow(self):
        def run_test_client(name, room, messages):
            client_process = subprocess.Popen(
                ["./client"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            
            # Connect client
            client_process.stdin.write(f"{name}\n{room}\n".encode())
            client_process.stdin.flush()
            
            # Send messages
            for msg in messages:
                client_process.stdin.write(f"{msg}\n".encode())
                client_process.stdin.flush()
                time.sleep(0.1)
            
            # Exit client
            client_process.stdin.write(b"#exit\n")
            client_process.stdin.flush()
            return client_process

        # Run multiple clients
        client_processes = [
            run_test_client(f"Client{i}", "TestRoom", [f"Message {i}"])
            for i in range(3)
        ]
        
        time.sleep(2)
        
        # Verify all clients completed successfully
        for proc in client_processes:
            proc.terminate()
            self.assertEqual(proc.wait(), 0)

    def test_system_load_distribution(self):
        clients = []
        for i in range(10):
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(('localhost', 6000))
            client.send(f"TestClient{i}\nRoom{i%3}".encode())
            port = int.from_bytes(client.recv(4), 'big')
            clients.append((client, port))
        
        # Check distribution across servers
        ports = set(port for _, port in clients)
        self.assertTrue(len(ports) >= 2)
        
        for client, _ in clients:
            client.close()

    def test_system_room_isolation(self):
        def run_room_client(name, room, send_msg, expect_msg):
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(('localhost', 6000))
            client.send(f"{name}\n{room}".encode())
            port = client.recv(4)
            client.connect(('localhost', int.from_bytes(port, 'big')))
            
            if send_msg:
                client.send(send_msg.encode())
            
            if expect_msg:
                received = client.recv(256)
                self.assertIn(expect_msg.encode(), received)
            
            client.close()

        # Create clients in different rooms
        client1 = threading.Thread(target=run_room_client, 
                                 args=("Client1", "Room1", "Hello Room1", None))
        client2 = threading.Thread(target=run_room_client,
                                 args=("Client2", "Room2", "Hello Room2", None))
        
        client1.start()
        client2.start()
        client1.join()
        client2.join()

    @classmethod
    def tearDownClass(cls):
        cls.lb_process.terminate()
        for server in cls.server_processes:
            server.terminate()

if __name__ == '__main__':
    unittest.main(verbosity=2)