import socket
import threading
from scapy.all import *
from scapy.all import ARP, Ether, srp
from scapy.config import conf
from scapy.layers import inet
import rsa
import ipaddress
import random as rnd
import numpy as np
import warnings


from ucimlrepo import fetch_ucirepo # dataset repository
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore") # evito un warning di scikit-learn dato dal dataset importato da ucimlrepo

class Client:
    def __init__(self, PORT):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.public_key, self.private_key = rsa.newkeys(2048)       #5120
        self.public_partner = None
        self.device_finder(PORT)
        
        
        while(True):
            self.nick = input(' Tell us your organization\' name: ')
            break
            
        self.stop_thread = False

        receive_thread = threading.Thread(target=self.receive)

        self.model = SGDClassifier()
        self.instanceN = 0
        self.weights, self.X_train, self.X_test, self.y_train, self.y_test = None, None, None, None, None
        self.model_setter()

        receive_thread.start()
    
    def receive(self):                                                                          # gestisco messaggi ricevuti dal server
        while True:
            try:
                message = rsa.decrypt(self.client.recv(2048), self.private_key).decode('ascii')
                if message == 'NICK':
                    self.client.send(rsa.encrypt(f"{self.nick} {self.instanceN}".encode('ascii'), self.public_partner))       
                elif message == 'GO':
                    self.train() 
                elif message.startswith('m1: '):
                    #print(f"\n\n{message}\n\n")
                    m1 = message.replace('m1: ', '')
                    ws1 = m1.strip('[]').split(', ')
                    self.weights = [float(weight) for weight in ws1]

                elif message.startswith('m2: '):
                    m2 = message.replace('m2: ', '')
                    ws2 = m2.strip('[]').split(', ')
                    w2 = [float(weight) for weight in ws2]
                    self.weights = self.weights + w2

                elif message.startswith('m3: '):
                    m3 = message.replace('m3: ', '')
                    ws3 = m3.strip('[]').split(', ')
                    w3 = [float(weight) for weight in ws3]
                    self.weights = self.weights + w3

                    print(f"\n\n New Weights: {self.weights}\n\n")
                    self.model.coef_[0] = np.array([self.weights])
                    
                elif message == 'FULL' or message == 'END':

                    if message == 'FULL':
                        print(" Server is full")
                    else:
                        print(" Server has been closed")

                    self.client.close()
                    self.stop_thread = True
                    break
                         
                else:
                    print(message)
            except Exception as e:
                print(f" Error: {str(e)}")
                self.client.close()
                self.stop_thread = True
                break

    def train(self):
        print(" Train is starting...")

        self.model.fit(self.X_train, self.y_train)

        # Valuta il modello sui dati di test
        y_pred = self.model.predict(self.X_test)
        accuracy = accuracy_score(self.y_test, y_pred)

        print(f" Accuratezza: {accuracy}\n")

        self.weights = self.model.coef_[0]
        weights_list = self.weights.flatten().tolist()  

        print(f"\n\n Train is finished (string). Weights: {weights_list}\n\n")

        self.client.send(rsa.encrypt(('m1: '+str(weights_list[:10])).encode('ascii'), self.public_partner))
        time.sleep(0.1)
        self.client.send(rsa.encrypt(('m2: '+str(weights_list[10:20])).encode('ascii'), self.public_partner))
        time.sleep(0.1)
        self.client.send(rsa.encrypt(('m3: '+str(weights_list[20:])).encode('ascii'), self.public_partner))
    
        print(" Waiting for the next train...\n")
    
    def device_finder(self, PORT):
        ip_list = []
    
        print(" Reaching the server...")
        target_ip = self.network_finder() 
        arp = ARP(pdst=target_ip)                                               # scansione Address Resolution Protocol (ARP)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")                                  # pacchetto ethernet indirizzo MAC broadcast
        packet = ether/arp
        result = srp(packet, timeout=3, verbose=0)[0]

        for sent, received in result:
            ip_list.append(received.psrc)
          
        ping = inet.IP(dst="8.8.8.8")/inet.ICMP()
        ip_list.append(ping.src)                                                # utilizzo un ping verso google (motivi pratici)
        ip_list.reverse()

        for ip in ip_list:
            try:
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)      # TCP
                client.connect((ip, PORT)) 
                self.client = client

                print(f' Connected to {ip}')
                self.public_partner = rsa.PublicKey.load_pkcs1(self.client.recv(2048))
                self.client.send(self.public_key.save_pkcs1("PEM"))
                break
            except Exception as e: 
                print(ip)
                print(f'{str(e)}')
                pass

    def network_finder(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)        # indirizzo IP dell' host, ipv4 e UDP
        s.connect(("8.8.8.8", 80))                                  # DNS di Google come riferimento
        ip = s.getsockname()[0]
        s.close()

        net = ipaddress.ip_interface(f'{ip}/24').network            # ottiene la subnet
        print(str(net))
        return str(net)
    
    def model_setter(self):
        # fetch dataset 
        breast_cancer_wisconsin_diagnostic = fetch_ucirepo(id=17) 
        
        # data (as pandas dataframes) 
        X = breast_cancer_wisconsin_diagnostic.data.features 
        y = breast_cancer_wisconsin_diagnostic.data.targets

        scaler = StandardScaler()
        X = scaler.fit_transform(X)                                                 # standardizzazione dei dati

        # metadata 
        #print(breast_cancer_wisconsin_diagnostic.metadata) 
         
        print(f"\n{breast_cancer_wisconsin_diagnostic.variables}\n")                        # documentazione var da dataset

        random_percentage = random.randint(30, 80)
        
        total_examples = len(y)                                                             # Numero totale di esempi
        self.instanceN = int((random_percentage / 100) * total_examples)
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(X, y, test_size=self.instanceN, random_state=42)

client = Client(60000)
