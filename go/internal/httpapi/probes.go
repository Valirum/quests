package httpapi

import (
	"context"
	"time"
)

const probeInterval = 15 * time.Second
const probeTimeout = 8 * time.Second

// RunProbes pings WebDAV and ClamAV on a timer. A websocket to the file
// server would be heavier than the question ("is it still there / did it
// come back?") and most DAV stacks don't push change events anyway.
func (s *Server) RunProbes(ctx context.Context) {
	s.probeOnce(ctx)
	ticker := time.NewTicker(probeInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.probeOnce(ctx)
		}
	}
}

func (s *Server) probeOnce(ctx context.Context) {
	if s.Health == nil {
		return
	}
	s.probeWebDAV(ctx)
	s.probeClamAV(ctx)
}

func (s *Server) probeWebDAV(ctx context.Context) {
	if s.WebDAV == nil || !s.WebDAV.Configured() {
		s.Health.SetProbe("webdav", "disabled", "not configured")
		return
	}
	pctx, cancel := context.WithTimeout(ctx, probeTimeout)
	defer cancel()
	if err := s.WebDAV.Ping(pctx); err != nil {
		s.Health.SetProbe("webdav", "offline", err.Error())
		return
	}
	s.Health.SetProbe("webdav", "ok", "")
}

func (s *Server) probeClamAV(ctx context.Context) {
	if s.ClamAV == nil || !s.ClamAV.Configured() {
		s.Health.SetProbe("clamav", "disabled", "not configured")
		return
	}
	pctx, cancel := context.WithTimeout(ctx, probeTimeout)
	defer cancel()
	if err := s.ClamAV.Ping(pctx); err != nil {
		s.Health.SetProbe("clamav", "offline", err.Error())
		return
	}
	s.Health.SetProbe("clamav", "ok", "")
}
