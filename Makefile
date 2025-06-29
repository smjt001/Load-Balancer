CXX = g++
CXXFLAGS = -Wall -Wextra -std=c++17 -O2

all: client server loadbalancer pinginfo

client: client.cpp
	$(CXX) $(CXXFLAGS) client.cpp -o client

server: server.cpp
	$(CXX) $(CXXFLAGS) server.cpp -o server

loadbalancer: loadbalancer.cpp
	$(CXX) $(CXXFLAGS) loadbalancer.cpp -o loadbalancer

pinginfo: pinginfo.cpp
	$(CXX) $(CXXFLAGS) pinginfo.cpp -o pinginfo

clean:
	rm -f client server loadbalancer pinginfo *.o

.PHONY: all clean