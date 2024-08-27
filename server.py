import threading        #gestione thread
import socket           #gestione comunicazione client-server
import subprocess       #gestione comunicazione shell
import rsa
import platform
import os
from threading import Lock 
import time

class Server:
    def __init__(self, PORT):

        self.lock = Lock()

        self.PORT = PORT
        self.get_private_ip()                                                                           # ottiene l'ip privato del server
        self.port_command_control = 0                                                                   # 0 = apre porte, 1 = chiude porte

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)                                 # crea un socket ipv4 e tcp
        self.server.bind((self.HOST, self.PORT))                                                        # collega il socket all'host e alla porta
        self.server.listen()                                                                            # mette il socket in ascolto

        self.clients = []
        self.organisations = []
        self.addresses = []
        self.public_partners = []
        self.running = True    
        self.total_instances = 0                                                                         # variabile per chiudere il server

        self.public_key, self.private_key = rsa.newkeys(2048)                                           # genero le chiavi pubbliche e private
        #pre: 2048, per 32 float mi servono almeno 5046 bit

        print(f'\n Opening incoming transmissions on port {self.PORT}')
        self.port_handler()                                                                             # apre la porta di comunicazione

        self.flowCtrl = True 

        while True:
            self.simulationCtrl = input(' How many iterations do you need to perform? ')                # controllo per la simulazione                                                                     
            self.clientsN = input(' How many clients do you want to connect? ')
            if self.clientsN.isdigit() and self.simulationCtrl.isdigit():
                self.clientsN = int(self.clientsN)
                self.simulationCtrl = int(self.simulationCtrl)
                break
            else:
                print(" Invalid input. Please enter a number.")

        self.weights = [[] for _ in range(self.clientsN)]
        self.clientsCtrlTrain = 0                                                                  # contatore per il controllo del training

        print(f"\n Server on: {self.HOST}:{self.PORT}\n")
        
        self.receive()                                                                                  # avvia il server                 

    def broadcast(self, message):                                                               # messaggio broadcast a tutti i client
        for client in self.clients:    
            client.send(rsa.encrypt(message, self.public_partners[self.clients.index(client)]))
    
    def weighted_average(self):
        print('\n Calculating weighted average...')

        if(self.total_instances == 0):
            self.total_instances = sum(int(inst[1]) for inst in self.organisations)  # Calcolo di total_instances una sola volta  
            print(' Calcolo istanze:', self.total_instances)      
        
        
        averages = [0 for _ in range(len(self.weights[1]))]

        for i in range(len(self.weights[1])):
            for j in range(len(self.organisations)):
                averages[i] += (float(self.weights[j][i]) * int(self.organisations[j][1])) 


        averages = [average/self.total_instances for average in averages]
        print(f'\n Weighted average: \n\n{averages}\n')
        
        self.broadcast(('m1: '+str(averages[:10])).encode('ascii'))
        time.sleep(0.1)
        self.broadcast(('m2: '+str(averages[10:20])).encode('ascii'))
        time.sleep(0.1)
        self.broadcast(('m3: '+str(averages[20:])).encode('ascii'))

        if self.simulationCtrl > 0:
            self.broadcast('GO'.encode('ascii'))


    def handler(self, client):                                                                          # gestisce i messaggi ricevuti dai client
        client.settimeout(0.5)
        while True:
            try:
                if self.running:
                    message = rsa.decrypt(client.recv(2048), self.private_key)
                    if message:
                        #print('messaggio')
                        msg = message.decode('ascii')
                        #print(f' {self.organisations[self.clients.index(client)][0]}: {msg}')

                        if msg.startswith('m1: '):
                            msg = msg.replace('m1: ', '')
                            weights = msg.strip('[]').split(', ')
                            self.weights[self.clients.index(client)] = [float(weight) for weight in weights]

                        if msg.startswith('m2: '):
                            msg = msg.replace('m2: ', '')
                            weights = msg.strip('[]').split(', ')
                            w2 = [float(weight) for weight in weights]
                            self.weights[self.clients.index(client)] = self.weights[self.clients.index(client)] + w2

                        if msg.startswith('m3: '):
                            self.lock.acquire()
                            try:
                                self.clientsCtrlTrain += 1

                                weights_string = msg.replace('m3: ', '')                              
                                
                                # Rimuove le parentesi quadre e divide la stringa in una lista basandosi sulla virgola
                                weights_list = weights_string.strip('[]').split(', ')
                                w3 = [float(weight) for weight in weights_list]
                                # Converte ogni elemento della lista in un intero
                                self.weights[self.clients.index(client)] = self.weights[self.clients.index(client)] + w3
                                print(f'\n Organization {self.organisations[self.clients.index(client)][0]} weights:\n\n{self.weights[self.clients.index(client)]}\n')
                                
                                if self.clientsCtrlTrain >= int(self.clientsN) and self.simulationCtrl > 0:
                                    self.clientsCtrlTrain = 0               # resetto il contatore di chi ha fatto il training
                                    self.simulationCtrl -= 1
                                    self.flowCtrl = True
                                    self.weighted_average()
                                    if self.simulationCtrl <= 0:
                                        self.broadcast('END'.encode('ascii'))
                                        #self.end_server()
                                        print('\n Simulation ended\n')
                                       
                            finally:
                                self.lock.release()

                    elif self.clientsN >= len(self.clients) and self.flowCtrl == True: # gestisco l'avvio dei training
                            self.broadcast('GO'.encode('ascii'))
                            self.flowCtrl = False

                    
                    else:
                        raise Exception(" Connection closed by client")
                    
                else:
                    raise Exception(" Server closed")                                                    # se il server è chiuso, solleva un'eccezione però server
                                                                                                        # restava collegato al client.recv in attesa di un messaggio
            except socket.timeout:                                                                      # quindi se non ricevo messaggi  passo alla iterazione successiva
                pass                                                                                    # e rivaluto la condizione del if self.running

            except Exception as e:
                if self.simulationCtrl > 0:
                    print(f' Error: {str(e)}')

                print(f' {self.organisations[self.clients.index(client)][0]} disconnected')

                if client in self.clients:
                    self.remove_client(client)
                    if len(self.organisations) == 0:
                        self.end_server()
                        print('\n')
                        

                break       
    
    def receive(self):                                                                                      # gestisce la connessione dei client
        while self.running:
            
            try:
                if(self.running):
                    if len(self.clients) == 0 and self.total_instances > 0:                                                  # se il numero di client connessi è minore del numero di client
                        raise Exception("No clients connected")                                                      # attesi, solleva un'eccezione
                    
                    client, address = self.server.accept()  

                    print(f' Connected with {str(address)}')
                    client.send(self.public_key.save_pkcs1("PEM")) 
                    pubkey = rsa.PublicKey.load_pkcs1(client.recv(2048))

                    if (len(self.clients)) < int(self.clientsN):                                                 

                        self.public_partners.append(pubkey)                          # riceve la chiave pubblica del client
                                
                        client.send(rsa.encrypt('NICK'.encode('ascii'), pubkey))                                                         
                        nick_and_instance = rsa.decrypt(client.recv(2048), self.private_key).decode('ascii')  
                        nick, instanceN = nick_and_instance.split(' ')
                        self.organisations.append([nick, instanceN])
                        self.weights.append([])
                        self.clients.append(client)
                        self.addresses.append(address)

                        print(f" Organisation's name of the client is {nick}, with instance number {instanceN}")
                        client.send(rsa.encrypt('Connected to the server'.encode('ascii'), pubkey))
                        thread = threading.Thread(target=self.handler, args=(client,))                              
                        thread.start() 

                        if len(self.clients) >= int(self.clientsN):
                            self.broadcast('GO'.encode('ascii'))
                            print("\n Simulation has started\n")

                    elif client:
                        client.send(rsa.encrypt('FULL'.encode('ascii'), pubkey))
                        client.close()
                        continue
                                                                           # parametri: metodo handler e connessione client                
            except Exception as e:
                # Chiudo la porta di comunicazione
                print(f'\n Closing transmissions on port {self.PORT}')
                self.port_handler()
                print(f' Port {self.PORT} closed\n')
                self.end_server()
                break

    
    def remove_client(self, client):
        index = self.clients.index(client)

        del self.clients[index]
        del self.organisations[index]
        del self.addresses[index]
        del self.public_partners[index]
        del self.weights[index]
        client.close()
    
    def get_private_ip(self):         
        if platform.system() != 'Windows':                                                                      # ottiene l'ip privato del server (caso Linux)
            command = "ifconfig | grep 'inet ' | awk '{print $2}' | grep -v '127.0.0.1'"
            process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
            output, error = process.communicate()
            if process.returncode == 0:
                self.HOST = output.decode('utf-8').strip()
            else:                                                                                               
                print(f" Error: {error.decode('utf-8')}")
                raise Exception('Error in getting private IP')
        else:                                                                                                   # (caso Windows)
            self.HOST = socket.gethostbyname(socket.gethostname())
            print(self.HOST)
            if not self.HOST:
                raise Exception('Error in getting private IP')
        
    def port_handler(self):        
        if platform.system() != 'Windows':                                                                         # apro e chiudo la porta di comunicazione (caso Linux)
            if self.port_command_control == 0:
                command = ['sudo', 'iptables', '-A', 'INPUT', '-p', 'tcp', '--dport', '60000', '-j', 'ACCEPT'] #open port
            elif self.port_command_control == 1:
                command = ['sudo', 'iptables', '-D', 'INPUT', '-p', 'tcp', '--dport', '60000', '-j', 'ACCEPT'] #close port
        
            self.port_command_control  += 1

            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            '''if result.returncode != 0:
                print('Error:', result.stderr.decode('utf-8'))'''

        else:                                                                                                     # (caso Windows, firwall avanzato di Windows deve essere abilitato)
            if self.port_command_control == 0:
                command = 'netsh advfirewall firewall add rule name="TCP Port Open" dir=in action=allow protocol=TCP localport=60000'
                command += ' & netsh advfirewall firewall add rule name="TCP Port Open" dir=out action=allow protocol=TCP localport=60000'
            elif self.port_command_control == 1:
                command = 'netsh advfirewall firewall delete rule name="TCP Port Open" protocol=TCP localport=60000'


            self.port_command_control += 1

            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            '''if result.returncode != 0 and result.stderr:
                print('Error:', result.stderr.decode('utf-8'))'''

    def end_server(self):                                                                                      # termino il server in maniera controllota
        # Chiudi il server e i client connessi

        self.running = False
        self.server.close()
        exit(0)


server = Server(60000)
