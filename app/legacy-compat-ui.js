(() => {
  // The base template still owns refreshAll(), setDecision() and application update
  // helpers. The modern review UI replaces the visible legacy jobs table, so route
  // every later loadJobs() call to the Job Review Queue instead of touching removed
  // jobsBody/jobsMinScore/jobsDecision elements.
  const routeLegacyJobsRefresh = async () => {
    if (typeof window.loadReviewJobs === 'function') {
      return window.loadReviewJobs();
    }
    return undefined;
  };

  window.loadJobs = routeLegacyJobsRefresh;
})();
