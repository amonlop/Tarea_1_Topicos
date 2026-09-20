CXX ?= g++
CXXFLAGS ?= -O2 -march=native -std=c++17 -Wall -Wextra

# Los ejecutables generados se guardan en la carpeta bin/.
BIN_DIR = bin

.PHONY: all clean

all: $(BIN_DIR)/pcap2bin $(BIN_DIR)/exact_hh $(BIN_DIR)/main_ventana

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

$(BIN_DIR)/pcap2bin: pcap2bin.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $<

$(BIN_DIR)/exact_hh: exact_hh.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $<

$(BIN_DIR)/main_ventana: main_ventana.cpp MurmurHash3.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $^

clean:
	rm -f $(BIN_DIR)/pcap2bin $(BIN_DIR)/exact_hh $(BIN_DIR)/main_ventana