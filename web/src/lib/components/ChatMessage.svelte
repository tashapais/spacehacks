<script lang="ts">
  type Citation = {
    id: string;
    title: string;
    url?: string;
  };

  export let message: {
    role: 'user' | 'assistant';
    text: string;
    isLoading?: boolean;
    citations?: Citation[];
  };
</script>

<div
  class="mb-4 flex w-full"
  class:justify-end={message.role === 'user'}
  class:justify-start={message.role === 'assistant'}
>
  <div
    class="max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm leading-relaxed shadow-sm transition-all duration-200"
    class:bg-blue-600={message.role === 'user'}
    class:text-white={message.role === 'user'}
    class:bg-gray-100={message.role === 'assistant'}
    class:text-gray-800={message.role === 'assistant' && !message.isLoading}
    class:text-gray-500={message.role === 'assistant' && message.isLoading}
    class:italic={message.isLoading}
  >
    <span>{message.text}</span>

    {#if message.citations?.length}
      <div class="mt-3 border-t border-gray-200 pt-2 text-xs text-gray-600">
        <div class="mb-1 font-semibold">Sources</div>
        <ul class="space-y-1">
          {#each message.citations as citation}
            <li>
              <span>[{citation.id}] {citation.title}</span>
              {#if citation.url}
                <a
                  class="ml-2 text-blue-600 hover:underline"
                  rel="noopener noreferrer"
                  target="_blank"
                  href={citation.url}
                  >Open</a
                >
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  </div>
</div>
