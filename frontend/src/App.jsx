import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, Bot } from 'lucide-react';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import Sidebar from './components/Sidebar';
import Aurora from './components/Aurora';
import { sendMessage } from './lib/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedModel, setSelectedModel] = useState('gpt');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(256); // Default width in pixels
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load conversations from localStorage on mount
  useEffect(() => {
    const savedConversations = localStorage.getItem('heritagebot_conversations');
    if (savedConversations) {
      const parsed = JSON.parse(savedConversations);
      setConversations(parsed);
      // Don't automatically load the first conversation - let user choose or start fresh
    }
  }, []);

  // Save conversations to localStorage whenever they change
  useEffect(() => {
    if (conversations.length > 0) {
      localStorage.setItem('heritagebot_conversations', JSON.stringify(conversations));
    }
  }, [conversations]);

  const handleSendMessage = async (userMessage) => {
    setError(null);
    
    const userMsg = {
      id: Date.now(),
      text: userMessage,
      isUser: true,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    // Add loading message
    const loadingMsg = {
      id: Date.now() + 1,
      text: '',
      isUser: false,
      modelId: selectedModel,
      timestamp: new Date().toISOString(),
      isTyping: true,
    };
    setMessages((prev) => [...prev, loadingMsg]);

    try {
      const response = await sendMessage(userMessage, selectedModel);
      
      // Replace loading message with actual response
      setMessages((prev) => 
        prev.map((msg) =>
          msg.id === loadingMsg.id
            ? { ...msg, text: response.answer, isTyping: false }
            : msg
        )
      );

      // Update current conversation
      if (currentConversationId) {
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === currentConversationId
              ? {
                  ...conv,
                  messages: [
                    ...conv.messages,
                    userMsg,
                    { ...loadingMsg, text: response.answer, isTyping: false },
                  ],
                  title: conv.title || userMessage.slice(0, 50),
                  messageCount: conv.messageCount + 2,
                }
              : conv
          )
        );
      } else {
        // Create new conversation
        const newConversation = {
          id: Date.now(),
          title: userMessage.slice(0, 50),
          messages: [userMsg, { ...loadingMsg, text: response.answer, isTyping: false }],
          messageCount: 2,
          createdAt: new Date().toISOString(),
        };
        setConversations((prev) => [newConversation, ...prev]);
        setCurrentConversationId(newConversation.id);
      }
    } catch (err) {
      setError(err.message || 'Failed to get response. Please try again.');
      // Remove loading message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== loadingMsg.id));
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setCurrentConversationId(null);
    setError(null);
  };

  const handleSelectConversation = (conversationId) => {
    const conversation = conversations.find((c) => c.id === conversationId);
    if (conversation) {
      setMessages(conversation.messages);
      setCurrentConversationId(conversationId);
      setError(null);
    }
  };

  const handleDeleteConversation = (conversationId) => {
    setConversations((prev) => prev.filter((c) => c.id !== conversationId));
    if (currentConversationId === conversationId) {
      handleNewChat();
    }
  };

  const handleSidebarWidthChange = (newWidth) => {
    setSidebarWidth(newWidth);
  };

  const showWelcome = messages.length === 0 && !error;

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        onWidthChange={handleSidebarWidthChange}
      />

      {/* Main Chat Area */}
      <main
        className={`flex-1 flex flex-col transition-all duration-300`}
        style={{ marginLeft: isSidebarCollapsed ? '0px' : `${sidebarWidth}px` }}
      >
        {/* Aurora Background - Fixed at bottom */}
        <div className="fixed bottom-0 left-0 right-0 h-96 pointer-events-none opacity-85 overflow-hidden z-0">
          <Aurora
            colorStops={["#F59E0B", "#D97706", "#F59E0B"]}
            blend={0.8}
            amplitude={1.4}
            speed={0.9}
          />
        </div>

        {/* Header */}
        <header className="border-b border-border/50 bg-background/95 backdrop-blur-md sticky top-0 z-30 shadow-sm">
          <div className="max-w-6xl mx-auto px-8 py-5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <a href="/" className="block hover:opacity-80 transition-opacity">
                <div>
                  <h1 className="text-xl font-bold">
                    <span className="bg-gradient-to-r from-amber-500 via-amber-400 to-yellow-400 bg-clip-text text-transparent">Heritage</span>
                    <span className="text-foreground">Bot</span>
                  </h1>
                  <p className="text-xs text-muted-foreground">Powered by AI</p>
                </div>
              </a>
            </div>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto bg-gradient-to-b from-background to-background/95">
          <div className="max-w-5xl mx-auto px-8 py-12">
            {/* Welcome Screen */}
            <AnimatePresence>
              {showWelcome && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="flex flex-col items-center justify-center min-h-[65vh] text-center px-4"
                >
                  <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.2, type: 'spring' }}
                    className="mb-6"
                  >
                    <img src="/Twinings-Gold-Logo.svg" alt="Twinings" className="w-96 h-96 object-contain" />
                  </motion.div>
                  <h2 className="text-5xl font-bold mb-5 tracking-tight text-center">Welcome to HeritageBot</h2>
                  <p className="text-muted-foreground text-lg max-w-2xl mb-4 leading-relaxed text-center mx-auto">
                    Ask me anything about Twinings, Ovaltine, or Associated British Foods.
                  </p>
                  <p className="text-muted-foreground/70 text-sm max-w-xl text-center mx-auto">
                    Powered by cutting-edge AI models for accurate, insightful answers.
                  </p>
                  <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl w-full mx-auto">
                    {[
                      'What is the history of Twinings?',
                      'Tell me about Ovaltine products',
                      'How is tea processed?',
                      "What are ABF's core values?",
                    ].map((suggestion, idx) => (
                      <motion.button
                        key={idx}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 + idx * 0.1 }}
                        whileHover={{ scale: 1.02, y: -2 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => handleSendMessage(suggestion)}
                        className="px-5 py-4 bg-card/60 backdrop-blur-sm border border-border/50 rounded-xl text-sm text-center hover:border-primary/30 hover:bg-card/80 transition-all shadow-sm hover:shadow-md"
                      >
                        {suggestion}
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error Message */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6 p-5 bg-destructive/10 border-2 border-destructive/30 rounded-xl flex items-start gap-4 text-destructive shadow-lg"
              >
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Error</p>
                  <p className="text-sm">{error}</p>
                </div>
              </motion.div>
            )}

            {/* Messages */}
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message.text}
                isUser={message.isUser}
                modelId={message.modelId}
                isTyping={message.isTyping}
              />
            ))}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="relative border-t border-border/50 bg-background/98 backdrop-blur-lg shadow-2xl z-10">
          <ChatInput 
              onSendMessage={handleSendMessage} 
              isLoading={isLoading}
              selectedModel={selectedModel}
              onModelChange={setSelectedModel}
            />
        </div>
      </main>
    </div>
  );
}

export default App;

