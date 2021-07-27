import socket
import re


def main():
    server1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP

    host = '10.50.177.208'
    port = 12345
    server1.bind((host, port))

    server1.listen(5)
    while True:
        conn, addr = server1.accept()
        print("----------------------------")
        print("Success connect from ", addr)

        try:
            count = 0
            while True:
                data = conn.recv(1024)
                data = re.split(r'[, :]', data.decode('utf-8'))  # 对收到的信息进行解析，包括dpid和port
                count += 1
                print("from {0}:dpid={1}, in_port={2}".format(addr, data[0], data[1]))
            conn.close()
        except Exception as error:  # 当控制器和应用层断开连接后，输出统计信息
            print('共接收{}条信息。'.format(count-1))
            print(error)
            exit()


if __name__ == '__main__':
    main()
