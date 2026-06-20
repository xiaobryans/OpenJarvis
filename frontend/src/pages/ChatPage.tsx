import { ChatArea } from '../components/Chat/ChatArea';
import { SystemPanel } from '../components/Chat/SystemPanel';
import { CloudStatusStrip } from '../components/Cloud/CloudStatusStrip';
import { useAppStore } from '../lib/store';

export function ChatPage() {
  const systemPanelOpen = useAppStore((s) => s.systemPanelOpen);

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex flex-col flex-1 min-w-0">
        <CloudStatusStrip />
        <div className="flex-1 min-h-0">
          <ChatArea />
        </div>
      </div>
      {systemPanelOpen && <SystemPanel />}
    </div>
  );
}
