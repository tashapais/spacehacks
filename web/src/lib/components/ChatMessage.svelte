<script lang="ts">
	export let message: {
		role: 'user' | 'assistant';
		text: string;
	};
</script>

<div
	class="mb-4 flex w-full"
	class:justify-end={message.role === 'user'}
	class:justify-start={message.role === 'assistant'}
>
	<div
		class="max-w-[80%] rounded-2xl px-4 py-2 text-sm
           leading-relaxed shadow-sm
           transition-all duration-200"
		class:bg-blue-600={message.role === 'user'}
		class:text-white={message.role === 'user'}
		class:bg-gray-100={message.role === 'assistant'}
		class:text-gray-800={message.role === 'assistant'}
	>
		{message.text}
	</div>
</div>
