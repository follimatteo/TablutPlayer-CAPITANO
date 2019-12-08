'''Client'''

import games
import tablut
import socket
import json
import numpy as np
import sys
import threading as t
import multiprocessing as mp
import time

move = None
m_value = - float('inf')
m_depth = 0
stop_flag = False
timeout = 55
ip_adress = "localhost"


def main():
    global timeout, ip_adress, move, m_value, m_depth, stop_flag      # shared variables
    act = mp.Queue()            # queue where we save the best intermediate move

    if len(sys.argv) != 3:
        exit(1)

    if sys.argv[0] == 'White':     # WIHITE port
        color = 'W'
        port = 5800
    elif sys.argv[0] == 'Black':   # BLACK port
        color = 'B'
        port = 5801
    else:
        exit(1)

    timeout = int(sys.argv[1])
    ip_adress = str(sys.argv[2])

    lock = t.Lock()     # lock needed to acces critical section (global move)

    client = Client(host, port)
    my_heuristic = tablut.Tablut(color).white_evaluation_function
    search = games.alphabeta_cutoff_search   # NB: my_games (not games)

    try:
        # present name
        client.send_name("capitano")

        # wait init state
        turn, state_np = client.recv_state()
        print(state_np, turn, "INITIAL STATE")

        # game loop:
        while True:
            if color == turn:
                # Timer used to not exceed the timeout
                tim = t.Timer(timeout, function=timer, args=[client, lock])
                tim.start()

                # MultiProcessing implementation
                processes = [mp.Process(target=actual, args=[act, i+1, search, turn, state_np, my_heuristic]) for i in range(3)]
                [process.start() for process in processes]
                print(state_np, "CHECK")

                while not stop_flag:
                    if not act.empty():
                        action, new_value, new_depth = act.get()
                        if m_depth == new_depth:
                            if new_value > m_value:
                                move = action
                                m_value = new_value
                                m_depth = new_depth
                        elif new_depth > m_depth:
                            move = action
                            m_value = new_value
                            m_depth = new_depth

                if stop_flag:
                    move = None
                    m_value = - float('inf')
                    stop_flag = False

                [process.terminate() for process in processes]
                tim.join()

                # move = search((turn, state_np), tablut.Tablut(), d=1, cutoff_test=None, eval_fn=my_heuristic)

            turn, state_np = client.recv_state()
            print (state_np, turn, "FINE TURNO")

    finally:
        print('closing socket')
        client.close()


class Client:

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

    def send_name(self, name):
        encoded = name.encode("UTF-8")
        length = len(encoded).to_bytes(4, 'big')
        self.sock.sendall(length+encoded)

    def send_move(self, move):
        move_obj = {
            "from": chr(97 + move[1]) + str(move[0]+1),
            "to": chr(97 + move[3]) + str(move[2]+1)
        }

        encoded = json.dumps(move_obj).encode("UTF-8")
        length = len(encoded).to_bytes(4, 'big')
        self.sock.sendall(length+encoded)

    def recv_state(self):
        char = self.sock.recv(1)
        while(char == b'\x00'):
            char = self.sock.recv(1)
        length_str = char + self.sock.recv(1)
        total = int.from_bytes(length_str, "big")
        state = self.sock.recv(total).decode("UTF-8")

        state = state.replace('EMPTY', 'e')
        state = state.replace('THRONE', 'e')
        state = state.replace('KING', 'k')
        state = state.replace('BLACK', 'b')
        state = state.replace('WHITE', 'w')

        state_dict = json.loads(state)
        matrix = np.array(state_dict['board'])

        return state_dict['turn'].capitalize(), matrix

    def close(self):
        self.sock.close()


def timer(client, lock):
    '''
    Handler of TIMER THREAD
    Function used to handle the timing contraints to produce an action
    '''
    global move, stop_flag

    lock.acquire()
    print("----------------------->", move)
    if move is not None:
        client.send_move(move)
    lock.release()

    stop_flag = True


def actual(act, part, search, turn, state_np, my_heuristic):
    '''
    Handler of PROCESSES
    Function used to search in a specific subdomain of possible actions
    '''
    for depth in range(1, 10):
        # NB: TWO (not one) VALUES RETURNED FROM SEARCH
        action, search_value = search((turn, state_np), tablut_noPrint.Tablut(color), d=depth, cutoff_test=None, eval_fn=my_heuristic, part=part)

        act.put((action, search_value, depth))


if __name__ == '__main__': main()
