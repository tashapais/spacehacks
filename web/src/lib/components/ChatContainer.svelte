<script lang="ts">
  import ChatMessage from '$lib/components/ChatMessage.svelte';
  import ChatInput from '$lib/components/ChatInput.svelte';
  import KnowledgeGraphPreview from '$lib/components/KnowledgeGraphPreview.svelte';

  type Citation = {
    id: string;
    title: string;
    url?: string;
  };

  type Message = {
    id: string;
    role: 'user' | 'assistant';
    text: string;
    isLoading?: boolean;
    citations?: Citation[];
  };

  let messageCounter = 0;

  const makeId = (prefix: string) => `${prefix}-${messageCounter++}`;

  let messages: Message[] = [
    {
      id: makeId('assistant'),
      role: 'assistant',
      text: 'Welcome to the NASA Bio Studies AI assistant! Ask me about space biology discoveries.'
    }
  ];

  // Extract session context from conversation
  $: sessionContext = messages
    .filter(msg => msg.role === 'user')
    .map(msg => msg.text)
    .join(' ')
    .split(/\s+/)
    .filter(word => word.length > 3) // Only words longer than 3 characters
    .slice(-20); // Last 20 words to keep context manageable

  const handleSend = async (text: string) => {
    if (!text.trim()) return;

    const userMessage: Message = { id: makeId('user'), role: 'user', text };
    const history = [...messages, userMessage];
    const placeholder: Message = {
      id: makeId('assistant'),
      role: 'assistant',
      text: 'Analyzing your question…',
      isLoading: true
    };

    messages = [...history, placeholder];

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ messages: history.map(({ role, text }) => ({ role, text })) })
      });

      const payload = await response.json();

      if (!response.ok || payload.error) {
        throw new Error(payload.error ?? 'Chat request failed');
      }

      messages = [
        ...history,
        {
          id: placeholder.id,
          role: 'assistant',
          text: payload.answer,
          citations: payload.citations
        }
      ];
    } catch (error) {
      console.error('Chat error', error);
      messages = [
        ...history,
        {
          id: placeholder.id,
          role: 'assistant',
          text: 'I ran into an issue retrieving that answer. Please try again later.'
        }
      ];
    }
  };
</script>

<div class="flex h-screen flex-col bg-gray-50">
  <div class="flex-1 space-y-2 overflow-y-auto px-6 py-4" style="scroll-behavior: smooth;">
    <KnowledgeGraphPreview compact={true} {sessionContext} />
    {#each messages as message (message.id)}
      <ChatMessage {message} />
    {/each}
  </div>

  <ChatInput onSend={handleSend} />
</div>
