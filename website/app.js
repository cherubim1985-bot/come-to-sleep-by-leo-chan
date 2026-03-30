const journeyButtons = document.querySelectorAll(".journey-button");
const sessionGrid = document.querySelector("#session-grid");
const libraryStatus = document.querySelector("#library-status");
const heroSessionImage = document.querySelector("#hero-session-image");
const heroSessionTitle = document.querySelector("#hero-session-title");
const heroSessionSubtitle = document.querySelector("#hero-session-subtitle");
const heroSessionAudio = document.querySelector("#hero-session-audio");
const heroSessionSource = document.querySelector("#hero-session-source");
const AUDIO_LOOP_WINDOW_SECONDS = 2 * 60 * 60;
const SITE_CONFIG = window.SITE_CONFIG || {};
const GA_MEASUREMENT_ID = String(SITE_CONFIG.gaMeasurementId || "").trim();
const MEDIA_BASE_URL = String(SITE_CONFIG.mediaBaseUrl || "").trim().replace(/\/+$/, "");

let activeJourney = "all";
let gaReady = false;

const JOURNEY_COPY = {
  all: "Start anywhere. These are the sessions most likely to help tonight.",
  overthinking: "Start here if the mind is still busy and bedtime feels mentally loud.",
  "night-waking": "Start here if you woke up in the night and want a gentler way back to sleep.",
  "world-nights": "Start here if you want atmosphere first: a softer place for the mind to land.",
};

function loadGa4() {
  if (!GA_MEASUREMENT_ID || gaReady) {
    return;
  }

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() {
    window.dataLayer.push(arguments);
  };

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GA_MEASUREMENT_ID)}`;
  document.head.appendChild(script);

  window.gtag("js", new Date());
  window.gtag("config", GA_MEASUREMENT_ID);
  gaReady = true;
}

function trackEvent(eventName, params = {}) {
  if (!GA_MEASUREMENT_ID) {
    return;
  }

  loadGa4();
  window.gtag("event", eventName, params);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[char];
  });
}

function resolvePosterPath(session) {
  return resolveAssetPath(session.publicPosterPath || session.posterPath || "");
}

function resolveMediaPath(session) {
  return resolveAssetPath(session.publicMediaPath || session.mediaPath || "");
}

function resolveAssetPath(pathValue) {
  const rawPath = String(pathValue || "").trim();
  if (!rawPath) {
    return "";
  }
  if (/^https?:\/\//i.test(rawPath)) {
    return rawPath;
  }
  if (!MEDIA_BASE_URL) {
    return rawPath;
  }

  const normalized = rawPath.replace(/^(\.\.\/|\.\/)+output\//, "");
  return normalized === rawPath ? rawPath : `${MEDIA_BASE_URL}/${normalized}`;
}

function renderMedia(session) {
  const mediaPath = resolveMediaPath(session);
  const posterPath = resolvePosterPath(session);

  if (session.kind === "video" && mediaPath) {
    return `
      <video controls preload="metadata" ${posterPath ? `poster="${escapeHtml(posterPath)}"` : ""}>
        <source src="${escapeHtml(mediaPath)}" type="video/mp4" />
      </video>
    `;
  }

  if (session.kind === "audio" && mediaPath) {
    return `
      <audio
        controls
        preload="metadata"
        data-loop-window-seconds="${AUDIO_LOOP_WINDOW_SECONDS}"
        data-session-slug="${escapeHtml(session.slug || "")}"
        data-session-title="${escapeHtml(session.title || "")}"
        data-session-meta="${escapeHtml(session.meta || "")}"
        data-source-section="library"
      >
        <source src="${escapeHtml(mediaPath)}" type="audio/mpeg" />
      </audio>
    `;
  }

  return `<div class="session-unavailable">This session is not ready to play yet.</div>`;
}

function renderSessionCover(session) {
  const posterPath = resolvePosterPath(session);
  const themeClass = escapeHtml(session.coverTheme || "warm-cover");
  const seriesLabel = String(session.series || "").trim();
  const bestForLabel = String(session.bestForLabel || "").trim();
  const metaBadges = `
    <div class="session-overlay-meta">
      ${seriesLabel ? `<span class="session-tag session-tag-secondary">${escapeHtml(seriesLabel)}</span>` : ""}
      ${bestForLabel ? `<span class="session-tag">${escapeHtml(bestForLabel)}</span>` : ""}
    </div>
  `;

  if (posterPath) {
    return `
      <div class="session-cover has-poster">
        <img
          class="session-cover-image"
          src="${escapeHtml(posterPath)}"
          alt="${escapeHtml(`${session.title} cover`)}"
          loading="lazy"
          decoding="async"
        />
        <div class="session-cover-copy">
          ${metaBadges}
          <h3>${escapeHtml(session.title)}</h3>
          <p>${escapeHtml(session.subtitle)}</p>
        </div>
      </div>
    `;
  }

  return `
    <div class="session-cover ${themeClass}">
      ${metaBadges}
      <h3>${escapeHtml(session.title)}</h3>
      <p>${escapeHtml(session.subtitle)}</p>
    </div>
  `;
}

function matchesJourney(session) {
  if (activeJourney === "all") {
    return true;
  }
  const tags = Array.isArray(session.bestFor) ? session.bestFor.map((item) => String(item).trim().toLowerCase()) : [];
  const seriesSlug = String(session.seriesSlug || "").trim().toLowerCase();
  return tags.includes(activeJourney) || seriesSlug === activeJourney;
}

function setupTimedAudioLoop(audio) {
  if (audio.dataset.loopBound === "true") {
    return;
  }

  audio.dataset.loopBound = "true";

  const loopWindowSeconds = Number(audio.dataset.loopWindowSeconds || AUDIO_LOOP_WINDOW_SECONDS);

  const ensurePlaybackSession = () => {
    if (!audio.dataset.playbackSessionId) {
      audio.dataset.playbackSessionId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      audio.dataset.startTracked = "";
      audio.dataset.thirtyTracked = "";
      audio.dataset.completeTracked = "";
      audio.dataset.pauseTrackedAt = "";
    }
  };

  const resetLoopSession = () => {
    audio.dataset.loopStartedAt = "";
    audio.dataset.playbackSessionId = "";
    audio.dataset.startTracked = "";
    audio.dataset.thirtyTracked = "";
    audio.dataset.completeTracked = "";
    audio.dataset.pauseTrackedAt = "";
  };

  const markLoopSessionStarted = () => {
    if (!audio.dataset.loopStartedAt) {
      audio.dataset.loopStartedAt = String(Date.now());
    }
  };

  audio.addEventListener("play", () => {
    ensurePlaybackSession();
    markLoopSessionStarted();

    if (audio.dataset.startTracked === "true") {
      return;
    }

    const durationSeconds = Number.isFinite(audio.duration) ? Math.round(audio.duration) : undefined;
    trackEvent("audio_play_start", {
      session_slug: audio.dataset.sessionSlug || "",
      session_title: audio.dataset.sessionTitle || "",
      session_category: audio.dataset.sessionMeta || "",
      source_section: audio.dataset.sourceSection || "",
      duration_seconds: durationSeconds,
    });
    audio.dataset.startTracked = "true";
  });

  audio.addEventListener("timeupdate", () => {
    ensurePlaybackSession();

    if (audio.dataset.thirtyTracked !== "true" && audio.currentTime >= 30) {
      trackEvent("audio_30_seconds", {
        session_slug: audio.dataset.sessionSlug || "",
        session_title: audio.dataset.sessionTitle || "",
        source_section: audio.dataset.sourceSection || "",
        listened_seconds: 30,
      });
      audio.dataset.thirtyTracked = "true";
    }

    const durationSeconds = Number.isFinite(audio.duration) ? audio.duration : 0;
    if (
      durationSeconds > 0 &&
      audio.dataset.completeTracked !== "true" &&
      audio.currentTime >= Math.max(durationSeconds - 1, durationSeconds * 0.98)
    ) {
      trackEvent("audio_complete", {
        session_slug: audio.dataset.sessionSlug || "",
        session_title: audio.dataset.sessionTitle || "",
        source_section: audio.dataset.sourceSection || "",
        duration_seconds: Math.round(durationSeconds),
      });
      audio.dataset.completeTracked = "true";
    }
  });

  audio.addEventListener("pause", () => {
    if (!audio.dataset.playbackSessionId) {
      return;
    }

    const currentSecond = Math.round(audio.currentTime || 0);
    if (audio.dataset.pauseTrackedAt === String(currentSecond)) {
      return;
    }

    trackEvent("audio_pause", {
      session_slug: audio.dataset.sessionSlug || "",
      session_title: audio.dataset.sessionTitle || "",
      source_section: audio.dataset.sourceSection || "",
      pause_second: currentSecond,
    });
    audio.dataset.pauseTrackedAt = String(currentSecond);
  });

  audio.addEventListener("ended", () => {
    const startedAt = Number(audio.dataset.loopStartedAt || 0);
    if (!startedAt) {
      return;
    }

    const elapsedSeconds = (Date.now() - startedAt) / 1000;
    if (elapsedSeconds < loopWindowSeconds) {
      audio.currentTime = 0;
      void audio.play().catch(() => {});
      return;
    }

    resetLoopSession();
  });
}

function bindAudioLoops() {
  if (heroSessionAudio) {
    setupTimedAudioLoop(heroSessionAudio);
  }
  const audioPlayers = sessionGrid.querySelectorAll("audio[data-loop-window-seconds]");
  audioPlayers.forEach(setupTimedAudioLoop);
}

function updateHeroSession(sessions) {
  if (!heroSessionImage || !heroSessionTitle || !heroSessionSubtitle) {
    return;
  }

  const latestSession = sessions[0];
  if (!latestSession) {
    return;
  }

  const posterPath = resolvePosterPath(latestSession);
  const mediaPath = resolveMediaPath(latestSession);

  if (posterPath) {
    heroSessionImage.src = posterPath;
  }
  heroSessionImage.alt = `${latestSession.title} cover`;
  heroSessionTitle.textContent = latestSession.title || "Tonight's Session";
  heroSessionSubtitle.textContent = latestSession.subtitle || latestSession.description || "A gentle session for tonight.";
  if (heroSessionAudio && heroSessionSource && mediaPath) {
    heroSessionAudio.dataset.sessionSlug = latestSession.slug || "";
    heroSessionAudio.dataset.sessionTitle = latestSession.title || "";
    heroSessionAudio.dataset.sessionMeta = latestSession.meta || "";
    heroSessionAudio.dataset.sourceSection = "hero";
    heroSessionSource.src = mediaPath;
    heroSessionAudio.load();
  }
}

function renderSessions(sessions) {
  const normalizedSessions = sessions.filter((session) => {
    const mediaPath = resolveMediaPath(session).toLowerCase();
    return session.kind === "audio" && mediaPath.endsWith(".mp3");
  });

  updateHeroSession(normalizedSessions);

  const filteredSessions = normalizedSessions.filter((session) => {
    return matchesJourney(session);
  });

  if (!filteredSessions.length) {
    sessionGrid.innerHTML = "";
    libraryStatus.textContent = "There are no sessions in this path yet.";
    return;
  }

  sessionGrid.innerHTML = filteredSessions
    .map((session) => {
      return `
        <article class="session-card" data-kind="${escapeHtml(session.kind)}">
          ${renderSessionCover(session)}
          <div class="session-body">
            <div class="session-card-meta">
              <p class="session-meta">${escapeHtml(session.meta)}</p>
              ${session.series ? `<p class="session-series">Series: ${escapeHtml(session.series)}</p>` : ""}
            </div>
            ${renderMedia(session)}
            <p class="session-description">${escapeHtml(session.description)}</p>
          </div>
        </article>
      `;
    })
    .join("");

  bindAudioLoops();
  const lead = JOURNEY_COPY[activeJourney] || JOURNEY_COPY.all;
  libraryStatus.textContent = `${lead} ${filteredSessions.length} gentle session${filteredSessions.length === 1 ? "" : "s"} available.`;
}

async function loadSessions() {
  try {
    const payload = window.SESSION_LIBRARY || { sessions: [] };
    renderSessions(Array.isArray(payload.sessions) ? payload.sessions : []);
  } catch (error) {
    sessionGrid.innerHTML = "";
    libraryStatus.textContent = "The session library is unavailable right now. Run the sync again to refresh this space.";
  }
}

journeyButtons.forEach((button) => {
  button.addEventListener("click", () => {
    activeJourney = button.dataset.journey || "all";
    journeyButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    loadSessions();
  });
});

loadSessions();
