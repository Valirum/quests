//go:build unix

package schedule

import (
	"os/exec"
	"syscall"
	"time"
)

// killTree makes a timed-out emit_pool_command die with everything it
// spawned. `sh -c "sleep 30; …"` forks sleep; killing only the shell leaves
// the child holding stdout open, so Run() would block until it exits on its
// own (the 20s timeout actually took 30s). The process group is killed and
// WaitDelay bounds the wait for the pipes.
func killTree(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Cancel = func() error { return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL) }
	cmd.WaitDelay = 2 * time.Second
}
