import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Send, StopCircle } from 'lucide-react';
import ModelSelector from './ModelSelector';

export default function ChatInput({ onSendMessage, isLoading, disabled, selectedModel, onModelChange }) {
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="w-full flex items-center justify-center px-6 pb-8 pt-4">
      <div className="w-full max-w-5xl">
        <form onSubmit={handleSubmit} className="relative">
          <div className="relative flex items-end gap-2 bg-card/80 backdrop-blur-sm border-2 border-border rounded-2xl shadow-xl p-2 focus-within:border-primary/40 transition-all">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about Twinings, Ovaltine, or ABF..."
            disabled={disabled || isLoading}
            rows={1}
            className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground px-5 py-3.5 resize-none outline-none min-h-[52px] max-h-[200px] text-[15px]"
          />

          <div className="flex items-center gap-2">
            <ModelSelector selectedModel={selectedModel} onModelChange={onModelChange} />
            
            <motion.button
              type="submit"
              disabled={!input.trim() || isLoading || disabled}
              whileHover={{ scale: input.trim() && !isLoading ? 1.05 : 1 }}
              whileTap={{ scale: input.trim() && !isLoading ? 0.95 : 1 }}
              className={`flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
                input.trim() && !isLoading
                  ? 'bg-primary text-primary-foreground hover:shadow-lg hover:shadow-primary/40'
                  : 'bg-secondary/50 text-muted-foreground cursor-not-allowed'
              }`}
            >
              {isLoading ? (
                <StopCircle className="w-5 h-5" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </motion.button>
          </div>
        </div>
      </form>
      </div>
    </div>
  );
}
