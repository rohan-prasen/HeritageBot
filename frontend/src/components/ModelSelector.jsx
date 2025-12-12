import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

const MODELS = [
  {
    id: 'gpt',
    name: 'GPT-5.1',
    color: '#F59E0B',
  },
  {
    id: 'claude',
    name: 'Claude Haiku 4.5',
    color: '#F59E0B',
  },
  {
    id: 'mistral',
    name: 'Mistral Large 3',
    color: '#F59E0B',
  },
  {
    id: 'grok',
    name: 'Grok 4',
    color: '#F59E0B',
  },
];

export default function ModelSelector({ selectedModel, onModelChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  const selectedModelData = MODELS.find((m) => m.id === selectedModel);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 bg-secondary/50 hover:bg-secondary border border-border rounded-lg text-sm font-medium transition-colors"
      >
        <span className="hidden sm:inline">{selectedModelData?.name}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${
          isOpen ? 'rotate-180' : ''
        }`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full mb-2 right-0 w-56 bg-card border border-border rounded-lg shadow-2xl overflow-hidden z-50"
          >
            <div className="p-1">
              {MODELS.map((model) => (
                <button
                  key={model.id}
                  onClick={() => {
                    onModelChange(model.id);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-end gap-3 px-3 py-2.5 rounded-md transition-colors text-left ${
                    selectedModel === model.id
                      ? 'bg-primary/10 text-foreground'
                      : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                  }`}
                >
                  <span className="font-medium text-sm leading-4">{model.name}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
