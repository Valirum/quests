package schedule

import (
	"context"
	"fmt"
	"net"
	"os"
	"path"
	"strconv"
	"strings"
	"time"

	"github.com/pkg/sftp"
	"golang.org/x/crypto/ssh"
)

// BackupRemote is the optional SFTP destination for DB + attachments artifacts
// (typically the workstation PC). Empty Host disables remote push.
type BackupRemote struct {
	Host string // "host" or "user@host"
	Dir  string // absolute directory on the remote
	Key  string // path to private key
	Port int    // 0 → 22
}

func (r BackupRemote) Configured() bool {
	return strings.TrimSpace(r.Host) != "" && strings.TrimSpace(r.Dir) != ""
}

// RemoteStore uploads/deletes named files under the configured remote directory.
type RemoteStore interface {
	Configured() bool
	Upload(ctx context.Context, localPath, remoteName string) error
	Remove(ctx context.Context, remoteName string) error
}

// NewSFTPRemote builds an SFTP-backed RemoteStore. Returns a no-op store when
// remote is not configured.
func NewSFTPRemote(r BackupRemote) RemoteStore {
	if !r.Configured() {
		return noopRemote{}
	}
	return &sftpRemote{cfg: r}
}

type noopRemote struct{}

func (noopRemote) Configured() bool { return false }
func (noopRemote) Upload(context.Context, string, string) error {
	return nil
}
func (noopRemote) Remove(context.Context, string) error { return nil }

type sftpRemote struct {
	cfg BackupRemote
}

func (r *sftpRemote) Configured() bool { return r.cfg.Configured() }

func (r *sftpRemote) withClient(ctx context.Context, fn func(*sftp.Client) error) error {
	client, err := r.dial(ctx)
	if err != nil {
		return err
	}
	defer client.Close()
	sftpClient, err := sftp.NewClient(client)
	if err != nil {
		return fmt.Errorf("sftp: %w", err)
	}
	defer sftpClient.Close()
	return fn(sftpClient)
}

func (r *sftpRemote) Upload(ctx context.Context, localPath, remoteName string) error {
	return r.withClient(ctx, func(c *sftp.Client) error {
		dir := strings.TrimRight(r.cfg.Dir, "/")
		if err := c.MkdirAll(dir); err != nil {
			return fmt.Errorf("mkdir %s: %w", dir, err)
		}
		remotePath := path.Join(dir, remoteName)
		src, err := os.Open(localPath)
		if err != nil {
			return err
		}
		defer src.Close()
		dst, err := c.Create(remotePath)
		if err != nil {
			return fmt.Errorf("create %s: %w", remotePath, err)
		}
		defer dst.Close()
		if _, err := dst.ReadFrom(src); err != nil {
			return fmt.Errorf("write %s: %w", remotePath, err)
		}
		return nil
	})
}

func (r *sftpRemote) Remove(ctx context.Context, remoteName string) error {
	return r.withClient(ctx, func(c *sftp.Client) error {
		remotePath := path.Join(strings.TrimRight(r.cfg.Dir, "/"), remoteName)
		err := c.Remove(remotePath)
		if err != nil && !os.IsNotExist(err) {
			// sftp may wrap; treat missing as ok
			if _, statErr := c.Stat(remotePath); statErr != nil {
				return nil
			}
			return err
		}
		return nil
	})
}

func (r *sftpRemote) dial(ctx context.Context) (*ssh.Client, error) {
	user, host := splitUserHost(r.cfg.Host)
	if user == "" {
		user = "root"
		if u := os.Getenv("USER"); u != "" {
			user = u
		}
	}
	port := r.cfg.Port
	if port <= 0 {
		port = 22
	}
	keyPath := strings.TrimSpace(r.cfg.Key)
	if keyPath == "" {
		return nil, fmt.Errorf("backup remote: QUESTS_BACKUP_REMOTE_KEY is empty")
	}
	keyPEM, err := os.ReadFile(keyPath)
	if err != nil {
		return nil, fmt.Errorf("read key %s: %w", keyPath, err)
	}
	signer, err := ssh.ParsePrivateKey(keyPEM)
	if err != nil {
		return nil, fmt.Errorf("parse key %s: %w", keyPath, err)
	}
	cfg := &ssh.ClientConfig{
		User:            user,
		Auth:            []ssh.AuthMethod{ssh.PublicKeys(signer)},
		HostKeyCallback: ssh.InsecureIgnoreHostKey(), // personal LAN / Tailscale
		Timeout:         20 * time.Second,
	}
	addr := net.JoinHostPort(host, strconv.Itoa(port))
	d := net.Dialer{Timeout: 20 * time.Second}
	conn, err := d.DialContext(ctx, "tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("dial %s: %w", addr, err)
	}
	sshConn, chans, reqs, err := ssh.NewClientConn(conn, addr, cfg)
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("ssh %s: %w", addr, err)
	}
	return ssh.NewClient(sshConn, chans, reqs), nil
}

func splitUserHost(raw string) (user, host string) {
	raw = strings.TrimSpace(raw)
	if i := strings.LastIndex(raw, "@"); i >= 0 {
		return raw[:i], raw[i+1:]
	}
	return "", raw
}
