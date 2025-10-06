<script lang="ts">
  import { marked } from 'marked';

  type Citation = {
    id: string;
    title: string;
    url?: string;
    snippet?: string;
  };

  export let message: {
    role: 'user' | 'assistant';
    text: string;
    isLoading?: boolean;
    citations?: Citation[];
  };

  $: renderedText = message.role === 'assistant' && !message.isLoading
    ? marked.parse(message.text, { async: false }) as string
    : message.text;
</script>

<div
  class="mb-4 flex w-full"
  class:justify-end={message.role === 'user'}
  class:justify-start={message.role === 'assistant'}
>
  <div
    class="max-w-[80%] rounded-2xl px-4 py-2 text-sm leading-relaxed shadow-sm transition-all duration-200"
    class:bg-blue-600={message.role === 'user'}
    class:text-white={message.role === 'user'}
    class:bg-gray-100={message.role === 'assistant'}
    class:text-gray-800={message.role === 'assistant' && !message.isLoading}
    class:text-gray-500={message.role === 'assistant' && message.isLoading}
    class:italic={message.isLoading}
    class:whitespace-pre-wrap={message.role === 'user' || message.isLoading}
  >
    {#if message.role === 'assistant' && !message.isLoading}
      <div class="prose prose-sm max-w-none prose-headings:font-bold prose-h1:text-lg prose-h2:text-base prose-h2:mt-4 prose-h2:mb-2 prose-p:my-2 prose-ul:my-2 prose-li:my-1">
        {@html renderedText}
      </div>
    {:else}
      <span>{message.text}</span>
    {/if}

    {#if message.citations?.length}
      <div class="mt-3 border-t border-gray-200 pt-2 text-xs text-gray-600">
        <div class="mb-1 font-semibold">Sources</div>
        <ul class="space-y-1">
          {#each message.citations as citation}
            <li>
              <div>
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
              </div>
              {#if citation.snippet}
                <div class="mt-0.5 text-[11px] text-gray-500 line-clamp-2">“{citation.snippet}”</div>
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  </div>
</div>
