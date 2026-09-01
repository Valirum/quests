package main

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"syscall"

	"golang.org/x/term"

	"github.com/valirum/quests/go/internal/auth"
	"github.com/valirum/quests/go/internal/config"
	"github.com/valirum/quests/go/internal/db"
)

const adminUsage = `quests-server admin commands (run on the host holding quests.db):

  quests-server useradd <username>       create an account (prompts for a password)
  quests-server passwd <username>        change an account's password
  quests-server users                    list accounts
  quests-server token add <name>         mint an API token for a headless client
  quests-server token ls                 list active API tokens
  quests-server token rm <id>            revoke an API token

Passwords are never taken from argv or env, so they stay out of shell history.
`

// runAdmin handles the bootstrap subcommands. Returns false if args are not an
// admin command, in which case the process starts the server as usual.
func runAdmin(args []string) bool {
	if len(args) == 0 {
		return false
	}
	switch args[0] {
	case "useradd", "passwd", "users", "token":
	case "help", "-h", "--help":
		fmt.Print(adminUsage)
		return true
	default:
		return false
	}

	config.LoadDotenv(config.Load().Root)
	cfg := config.Load()
	sqlDB, err := db.Open(cfg.DBPath)
	if err != nil {
		fatal("db: %v", err)
	}
	defer sqlDB.Close()
	st := &auth.Store{DB: sqlDB}

	switch args[0] {
	case "useradd":
		if len(args) < 2 {
			fatal("usage: quests-server useradd <username>")
		}
		pw := promptNewPassword()
		u, err := st.CreateUser(args[1], pw)
		if err != nil {
			if errors.Is(err, auth.ErrUserExists) {
				fatal("account %q already exists", args[1])
			}
			fatal("%v", err)
		}
		fmt.Printf("created account %q (id=%d)\n", u.Username, u.ID)
		fmt.Println("auth is now enforced on this instance — restart the server to apply.")
	case "passwd":
		if len(args) < 2 {
			fatal("usage: quests-server passwd <username>")
		}
		pw := promptNewPassword()
		if err := st.SetPassword(args[1], pw); err != nil {
			fatal("%v", err)
		}
		fmt.Println("password updated")
	case "users":
		users, err := st.ListUsers()
		if err != nil {
			fatal("%v", err)
		}
		if len(users) == 0 {
			fmt.Println("no accounts yet — create one with: quests-server useradd <username>")
			return true
		}
		for _, u := range users {
			state := "active"
			if !u.IsActive {
				state = "disabled"
			}
			fmt.Printf("%d\t%s\t%s\n", u.ID, u.Username, state)
		}
	case "token":
		runTokenCmd(st, args[1:])
	}
	return true
}

func runTokenCmd(st *auth.Store, args []string) {
	if len(args) == 0 {
		fatal("usage: quests-server token add|ls|rm")
	}
	switch args[0] {
	case "add":
		if len(args) < 2 {
			fatal("usage: quests-server token add <name>   (e.g. overlay, telegram, cli)")
		}
		users, err := st.ListUsers()
		if err != nil {
			fatal("%v", err)
		}
		if len(users) == 0 {
			fatal("create an account first: quests-server useradd <username>")
		}
		owner := users[0]
		if len(args) >= 3 {
			owner = auth.User{}
			for _, u := range users {
				if u.Username == strings.ToLower(args[2]) {
					owner = u
				}
			}
			if owner.ID == 0 {
				fatal("no such account: %s", args[2])
			}
		}
		secret, err := st.CreateAPIToken(owner.ID, args[1])
		if err != nil {
			fatal("%v", err)
		}
		fmt.Printf("token for %q (owner %s):\n\n  %s\n\n", args[1], owner.Username, secret)
		fmt.Println("Shown once — only its hash is stored. Put it in the client's env:")
		fmt.Printf("  QUESTS_API_TOKEN=%s\n", secret)
	case "ls":
		toks, err := st.ListAPITokens()
		if err != nil {
			fatal("%v", err)
		}
		if len(toks) == 0 {
			fmt.Println("no active tokens")
			return
		}
		for _, t := range toks {
			last := "never"
			if t.LastUsedAt != nil {
				last = *t.LastUsedAt
			}
			fmt.Printf("%d\t%s\t%s\tlast_used=%s\n", t.ID, t.Name, t.Username, last)
		}
	case "rm":
		if len(args) < 2 {
			fatal("usage: quests-server token rm <id>")
		}
		id, err := strconv.ParseInt(args[1], 10, 64)
		if err != nil {
			fatal("token id must be a number")
		}
		if err := st.RevokeAPIToken(id); err != nil {
			fatal("%v", err)
		}
		fmt.Println("revoked")
	default:
		fatal("unknown token command %q", args[0])
	}
}

// promptNewPassword reads a password twice without echoing it. On a non-TTY
// (CI, docker exec without -t) it falls back to reading one line from stdin.
func promptNewPassword() string {
	if !term.IsTerminal(int(syscall.Stdin)) {
		sc := bufio.NewScanner(os.Stdin)
		if !sc.Scan() {
			fatal("no password on stdin")
		}
		pw := strings.TrimSpace(sc.Text())
		if len([]rune(pw)) < 8 {
			fatal("password must be at least 8 characters")
		}
		return pw
	}
	fmt.Print("New password: ")
	first, err := term.ReadPassword(int(syscall.Stdin))
	fmt.Println()
	if err != nil {
		fatal("read password: %v", err)
	}
	fmt.Print("Repeat password: ")
	second, err := term.ReadPassword(int(syscall.Stdin))
	fmt.Println()
	if err != nil {
		fatal("read password: %v", err)
	}
	if string(first) != string(second) {
		fatal("passwords do not match")
	}
	if len([]rune(string(first))) < 8 {
		fatal("password must be at least 8 characters")
	}
	return string(first)
}

func fatal(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "error: "+format+"\n", a...)
	os.Exit(1)
}
