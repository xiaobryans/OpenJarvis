import { ChatArea } from '../components/Chat/ChatArea';
import { CloudStatusStrip } from '../components/Cloud/CloudStatusStrip';

export function ChatPage() {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <CloudStatusStrip />
      <div className="flex-1 min-h-0">
        <ChatArea />
      </div>
    </div>
  );
}
