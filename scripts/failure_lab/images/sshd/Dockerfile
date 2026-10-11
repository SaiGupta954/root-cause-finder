FROM alpine:3.20
RUN apk add --no-cache openssh \
 && ssh-keygen -A \
 && echo "root:Sup3r-Secret-Lab-Pass" | chpasswd \
 && adduser -D deploy && echo "deploy:deploy-lab-pass-42" | chpasswd \
 && sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/; s/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
CMD ["/usr/sbin/sshd", "-D", "-e"]
