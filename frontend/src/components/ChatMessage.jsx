import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';
import { Bot } from 'lucide-react';

const MODEL_COLORS = {
  gpt: '#F59E0B',
  claude: '#F59E0B',
  mistral: '#F59E0B',
  grok: '#F59E0B',
};

const MODEL_NAMES = {
  gpt: 'GPT-5.1',
  claude: 'Claude Haiku 4.5',
  mistral: 'Mistral Large 3',
  grok: 'Grok 4',
};

export default function ChatMessage({ message, isUser, modelId, isTyping }) {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (isUser || !message) {
      setDisplayedText(message);
      setIsComplete(true);
      return;
    }

    // Typing animation for AI messages
    let currentIndex = 0;
    setDisplayedText('');
    setIsComplete(false);

    const interval = setInterval(() => {
      if (currentIndex <= message.length) {
        setDisplayedText(message.slice(0, currentIndex));
        currentIndex++;
      } else {
        setIsComplete(true);
        clearInterval(interval);
      }
    }, 15);

    return () => clearInterval(interval);
  }, [message, isUser]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-8`}
    >
      <div className={`flex gap-4 max-w-[80%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div
          className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center ${
            isUser
              ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/30'
              : 'bg-card border-2 border-border text-muted-foreground'
          }`}
        >
          {isUser ? (
            <span className="text-[10px] font-bold">You</span>
          ) : (
            <Bot className="w-4 h-4" style={{ color: MODEL_COLORS[modelId] }} />
          )}
        </div>

        {/* Message Content */}
        <div className="flex flex-col gap-2 flex-1">
          {/* Model Indicator for AI messages */}
          {!isUser && modelId && (
            <div className="flex items-center gap-2">
              <span
                className="text-xs font-semibold px-2.5 py-1 rounded-lg"
                style={{
                  backgroundColor: `${MODEL_COLORS[modelId]}15`,
                  color: MODEL_COLORS[modelId],
                }}
              >
                {MODEL_NAMES[modelId]}
              </span>
            </div>
          )}

          {/* Message Bubble */}
          <div
            className={`rounded-2xl px-6 py-4 ${
              isUser
                ? 'bg-primary text-primary-foreground shadow-md'
                : 'bg-card/60 backdrop-blur-sm border border-border text-foreground'
            }`}
          >
            <div className="whitespace-pre-wrap break-words text-[15px] leading-relaxed">
              {isTyping && !isUser ? (
                <div className="flex gap-1">
                  <motion.span
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: 0 }}
                    className="w-2 h-2 bg-current rounded-full"
                  />
                  <motion.span
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: 0.2 }}
                    className="w-2 h-2 bg-current rounded-full"
                  />
                  <motion.span
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: 0.4 }}
                    className="w-2 h-2 bg-current rounded-full"
                  />
                </div>
              ) : (
                <>
                  {displayedText}
                  {!isComplete && !isUser && (
                    <motion.span
                      animate={{ opacity: [1, 0] }}
                      transition={{ duration: 0.8, repeat: Infinity }}
                      className="inline-block w-1 h-4 bg-current ml-0.5 align-middle"
                    />
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
