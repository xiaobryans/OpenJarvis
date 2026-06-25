import { useEffect, useState, useCallback, useRef } from 'react';
import { Routes, Route } from 'react-router';
import { Layout } from './components/Layout';
import { ChatPage } from './pages/ChatPage';
import { JarvisHomePage } from './components/Jarvis/JarvisHomePage';
import { JarvisCockpitPage } from './pages/JarvisCockpitPage';
import { DashboardPage } from './pages/DashboardPage';
import { SettingsPage } from './pages/SettingsPage';
import { GetStartedPage } from './pages/GetStartedPage';
import { AgentsPage } from './pages/AgentsPage';
import { DataSourcesPage } from './pages/DataSourcesPage';
import { LogsPage } from './pages/LogsPage';
import { MissionControlPage } from './pages/MissionControlPage';
import { MobilePage } from './pages/MobilePage';
import { WorkbenchPage } from './pages/WorkbenchPage';
import { AuthorityPage } from './pages/AuthorityPage';
import { RulesManagerPage } from './pages/RulesManagerPage';
import { ExpertRolesPage } from './pages/ExpertRolesPage';
import { JarvisCapabilitiesPage } from './pages/JarvisCapabilitiesPage';
import { DelegationPage } from './pages/DelegationPage';
import { FollowUpCenterPage } from './pages/FollowUpCenterPage';
import { RoutinesCenterPage } from './pages/RoutinesCenterPage';
import { MemoryOSPage } from './pages/MemoryOSPage';
import { CommandCenterPage } from './pages/CommandCenterPage';
import { SkillsPluginsPage } from './pages/SkillsPluginsPage';
import { ConnectorWorkflowsPage } from './pages/ConnectorWorkflowsPage';
import { ProactiveOperatorPage } from './pages/ProactiveOperatorPage';
import { BusinessAdminPage } from './pages/BusinessAdminPage';
import { ObservabilityPage } from './pages/ObservabilityPage';
import { LongHorizonGoalsPage } from './pages/LongHorizonGoalsPage';
import { FinanceAdminOSPage } from './pages/FinanceAdminOSPage';
import { ResearchOSPage } from './pages/ResearchOSPage';
import { BrowserOperatorPage } from './pages/BrowserOperatorPage';
import { MemoryGraphPage } from './pages/MemoryGraphPage';
import { MultiDevicePage } from './pages/MultiDevicePage';
import { MarketplacePage } from './pages/MarketplacePage';
import { OrgModePage } from './pages/OrgModePage';
import { DeviceControllerPage } from './pages/DeviceControllerPage';
import { AutonomousOrgPage } from './pages/AutonomousOrgPage';
import { MissionControlCPage } from './pages/MissionControlCPage';
import { ReviewGovernancePage } from './pages/ReviewGovernancePage';
import { ProductReadinessPage } from './pages/ProductReadinessPage';
import { MarketplaceGovernancePage } from './pages/MarketplaceGovernancePage';
import { EnterpriseGovernancePage } from './pages/EnterpriseGovernancePage';
import { ScaleControlPage } from './pages/ScaleControlPage';
import { CompanyOSPage } from './pages/CompanyOSPage';
import { SafetySimulationPage } from './pages/SafetySimulationPage';
import { ControlTowerPage } from './pages/ControlTowerPage';
import { CommandPalette } from './components/CommandPalette';
import { TextFallbackPanel } from './components/TextFallbackPanel';
import { SetupScreen } from './components/SetupScreen';
import { Toaster } from './components/ui/sonner';
import { useAppStore } from './lib/store';
import { fetchModels, fetchServerInfo, fetchSavings, submitSavings, isTauri, apiFetch } from './lib/api';
import { OptInModal } from './components/OptInModal';
import { UpdateChecker } from './components/Desktop/UpdateChecker';
import { track, hashId } from './lib/analytics';

export default function App() {
  const [setupDone, setSetupDone] = useState(!isTauri());
  const handleSetupReady = useCallback(() => {
    setSetupDone(true);
    // Only fire once per install — guard against setup screen re-appearing
    // on reinstalls or dev reloads.
    if (!localStorage.getItem('oj-setup-completed')) {
      localStorage.setItem('oj-setup-completed', '1');
      track('setup_completed', { preset: 'default' });
    }
  }, []);
  const prevModelRef = useRef<string>('');
  const setModels = useAppStore((s) => s.setModels);
  const setModelsLoading = useAppStore((s) => s.setModelsLoading);
  const setSelectedModel = useAppStore((s) => s.setSelectedModel);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const setServerInfo = useAppStore((s) => s.setServerInfo);
  const setSavings = useAppStore((s) => s.setSavings);
  const settings = useAppStore((s) => s.settings);
  const commandPaletteOpen = useAppStore((s) => s.commandPaletteOpen);
  const textFallbackOpen = useAppStore((s) => s.textFallbackOpen);
  const setTextFallbackOpen = useAppStore((s) => s.setTextFallbackOpen);
  const optInEnabled = useAppStore((s) => s.optInEnabled);
  const optInDisplayName = useAppStore((s) => s.optInDisplayName);
  const optInEmail = useAppStore((s) => s.optInEmail);
  const optInAnonId = useAppStore((s) => s.optInAnonId);
  const optInModalSeen = useAppStore((s) => s.optInModalSeen);
  const optInModalOpen = useAppStore((s) => s.optInModalOpen);
  const setOptInModalOpen = useAppStore((s) => s.setOptInModalOpen);
  const markOptInModalSeen = useAppStore((s) => s.markOptInModalSeen);
  const savings = useAppStore((s) => s.savings);

  // Apply theme class to <html>
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('dark', 'light');
    if (settings.theme === 'dark') root.classList.add('dark');
    else if (settings.theme === 'light') root.classList.add('light');
  }, [settings.theme]);

  // Sync overlay conversations into the main app
  const importOverlay = useAppStore((s) => s.importOverlayConversation);
  useEffect(() => {
    if (!isTauri()) return;
    importOverlay();
    const interval = setInterval(importOverlay, 5000);
    return () => clearInterval(interval);
  }, [importOverlay]);

  // Fetch models on mount
  useEffect(() => {
    fetchModels()
      .then((m) => {
        setModels(m);
        if (!selectedModel && m.length > 0) setSelectedModel(m[0].id);
      })
      .catch(() => setModels([]))
      .finally(() => setModelsLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch server info
  useEffect(() => {
    fetchServerInfo().then(setServerInfo).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Override selectedModel with configured PA front-door cloud model.
  // Local Ollama models (e.g. qwen3.5:2b) are only used if no cloud route exists.
  // Cloud model IDs contain '/' (e.g. openai/gpt-4o); local IDs do not.
  useEffect(() => {
    apiFetch('/v1/model-routing/status')
      .then((r) => r.json())
      .then((d: { pa_front_door_model?: string }) => {
        const pa = d?.pa_front_door_model;
        if (pa && pa.includes('/')) setSelectedModel(pa);
      })
      .catch(() => {}); // non-critical — silent on failure
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll savings and optionally share to Supabase
  useEffect(() => {
    const refresh = () =>
      fetchSavings()
        .then((data) => {
          setSavings(data);
          if (optInEnabled && optInDisplayName && data) {
            const claudeEntry = data.per_provider.find(
              (p) => p.provider === 'claude-opus-4.6',
            );
            const dollarSavings = claudeEntry ? claudeEntry.total_cost : 0;
            const energySaved = data.per_provider.reduce(
              (sum, p) => sum + (p.energy_wh || 0),
              0,
            );
            const flopsSaved = data.per_provider.reduce(
              (sum, p) => sum + (p.flops || 0),
              0,
            );
            submitSavings({
              anon_id: optInAnonId,
              display_name: optInDisplayName,
              email: optInEmail,
              total_calls: data.total_calls,
              total_tokens: data.total_tokens,
              dollar_savings: dollarSavings,
              energy_wh_saved: energySaved,
              flops_saved: flopsSaved,
              token_counting_version: data.token_counting_version ?? 1,
            });
          }
        })
        .catch(() => {});
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [optInEnabled, optInDisplayName, optInAnonId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Show opt-in modal on first visit
  useEffect(() => {
    if (!optInModalSeen) {
      setOptInModalOpen(true);
      markOptInModalSeen();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fire model_changed when the user switches models. First mount is
  // not a "change" — only emit when both prev and current are real and
  // differ.
  useEffect(() => {
    const prev = prevModelRef.current;
    const curr = selectedModel || '';
    prevModelRef.current = curr;
    if (!prev || !curr || prev === curr) return;
    void (async () => {
      const [fromHash, toHash] = await Promise.all([
        hashId(prev),
        hashId(curr),
      ]);
      track('model_changed', {
        from_model_hash: fromHash,
        to_model_hash: toHash,
      });
    })();
  }, [selectedModel]);

  // app_opened — one-shot per app launch, fires after analytics has had
  // a chance to initialize. platform + version are super-properties
  // registered in analytics.ts initAnalytics, so no per-call props needed.
  useEffect(() => {
    const t = setTimeout(() => {
      track('app_opened', {});
    }, 500);
    return () => clearTimeout(t);
  }, []);

  const toggleSystemPanel = useAppStore((s) => s.toggleSystemPanel);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K opens ONLY the text/transcript/chat fallback — never the model
      // or settings picker. Model routing is automatic/internal.
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setTextFallbackOpen(!textFallbackOpen);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'i') {
        e.preventDefault();
        toggleSystemPanel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [textFallbackOpen, setTextFallbackOpen, toggleSystemPanel]);


  if (!setupDone) {
    return <SetupScreen onReady={handleSetupReady} />;
  }

  return (
    <>
      <UpdateChecker />
      <Routes>
        <Route path="mobile" element={<MobilePage />} />
        <Route element={<Layout />}>
          <Route index element={<JarvisCockpitPage />} />
          <Route path="classic" element={<JarvisHomePage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="get-started" element={<GetStartedPage />} />
          <Route path="data-sources" element={<DataSourcesPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="logs" element={<LogsPage />} />
          <Route path="mission-control" element={<MissionControlPage />} />
          <Route path="workbench" element={<WorkbenchPage />} />
          <Route path="authority" element={<AuthorityPage />} />
          <Route path="rules" element={<RulesManagerPage />} />
          <Route path="expert-roles" element={<ExpertRolesPage />} />
          <Route path="capabilities" element={<JarvisCapabilitiesPage />} />
          <Route path="delegation" element={<DelegationPage />} />
          <Route path="follow-ups" element={<FollowUpCenterPage />} />
          <Route path="routines" element={<RoutinesCenterPage />} />
          <Route path="memory-os" element={<MemoryOSPage />} />
          <Route path="command-center" element={<CommandCenterPage />} />
          <Route path="skills-plugins" element={<SkillsPluginsPage />} />
          <Route path="connector-workflows" element={<ConnectorWorkflowsPage />} />
          <Route path="proactive" element={<ProactiveOperatorPage />} />
          <Route path="business-admin" element={<BusinessAdminPage />} />
          <Route path="observability" element={<ObservabilityPage />} />
          <Route path="long-horizon" element={<LongHorizonGoalsPage />} />
          <Route path="finance-admin" element={<FinanceAdminOSPage />} />
          <Route path="research-os" element={<ResearchOSPage />} />
          <Route path="browser-operator" element={<BrowserOperatorPage />} />
          <Route path="memory-graph" element={<MemoryGraphPage />} />
          <Route path="multi-device" element={<MultiDevicePage />} />
          <Route path="marketplace" element={<MarketplacePage />} />
          <Route path="org-mode" element={<OrgModePage />} />
          <Route path="device-controller" element={<DeviceControllerPage />} />
          <Route path="autonomous-org" element={<AutonomousOrgPage />} />
          <Route path="mission-control-c" element={<MissionControlCPage />} />
          <Route path="review-governance" element={<ReviewGovernancePage />} />
          <Route path="product-readiness" element={<ProductReadinessPage />} />
          <Route path="marketplace-governance" element={<MarketplaceGovernancePage />} />
          <Route path="enterprise-governance" element={<EnterpriseGovernancePage />} />
          <Route path="scale-control" element={<ScaleControlPage />} />
          <Route path="company-os" element={<CompanyOSPage />} />
          <Route path="safety-simulation" element={<SafetySimulationPage />} />
          <Route path="control-tower" element={<ControlTowerPage />} />
        </Route>
      </Routes>
      <Toaster position="bottom-right" />
      {commandPaletteOpen && <CommandPalette />}
      {textFallbackOpen && <TextFallbackPanel />}
      {optInModalOpen && (
        <OptInModal onClose={() => setOptInModalOpen(false)} />
      )}
    </>
  );
}
