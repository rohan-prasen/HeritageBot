import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Plus, Trash2, ChevronLeft, ChevronRight, MoreVertical, Pencil } from 'lucide-react';
import { useState, useRef, useCallback, useEffect } from 'react';

export default function Sidebar({ 
  conversations, 
  currentConversationId, 
  onNewChat, 
  onSelectConversation, 
  onDeleteConversation,
  isCollapsed,
  onToggleCollapse,
  onWidthChange 
}) {
  const [openMenuId, setOpenMenuId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [sidebarWidth, setSidebarWidth] = useState(256); // Default width in pixels
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef(null);

  const handleRename = (conversationId, newTitle) => {
    // This would need to be passed from parent component
    console.log('Rename conversation', conversationId, newTitle);
    setRenamingId(null);
  };

  const handleMouseDown = useCallback((e) => {
    setIsResizing(true);
    e.preventDefault();
  }, []);

  const handleMouseMove = useCallback((e) => {
    if (!isResizing) return;
    
    const newWidth = Math.max(200, Math.min(500, e.clientX));
    setSidebarWidth(newWidth);
    if (onWidthChange) {
      onWidthChange(newWidth);
    }
  }, [isResizing, onWidthChange]);

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
  }, []);

  // Add global mouse event listeners when resizing
  useEffect(() => {
    if (isResizing) {
      document.body.style.cursor = 'col-resize';
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.body.style.cursor = '';
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isResizing, handleMouseMove, handleMouseUp]);

  return (
    <>
      {/* Toggle Button */}
      <motion.button
        onClick={onToggleCollapse}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className={`fixed top-6 z-50 w-10 h-10 bg-card/90 backdrop-blur-md border-2 border-border rounded-xl flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-primary/50 hover:bg-card transition-all shadow-lg ${
          isCollapsed ? 'left-6' : `left-[${sidebarWidth + 16}px]`
        }`}
      >
        {isCollapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
      </motion.button>

      {/* Sidebar */}
      <AnimatePresence>
        {!isCollapsed && (
          <motion.aside
            ref={sidebarRef}
            initial={{ x: -sidebarWidth }}
            animate={{ x: 0 }}
            exit={{ x: -sidebarWidth }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed left-0 top-0 h-full bg-sidebar/98 backdrop-blur-lg border-r-2 border-sidebar-border/50 flex flex-col z-40 shadow-2xl"
            style={{ width: `${sidebarWidth}px` }}
          >
            {/* Resize Handle */}
            <div
              className={`absolute right-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-primary/50 active:bg-primary transition-colors z-50 group ${
                isResizing ? 'bg-primary/30' : ''
              }`}
              onMouseDown={handleMouseDown}
            >
              <div className={`absolute right-0 top-1/2 transform -translate-y-1/2 w-0.5 h-8 bg-border group-hover:bg-primary/70 rounded-full transition-colors ${
                isResizing ? 'bg-primary' : ''
              }`} />
            </div>

            {/* Header */}
            <div className="p-5 border-b border-sidebar-border/50">
              <motion.button
                onClick={onNewChat}
                whileTap={{ scale: 0.98 }}
                className="w-full flex items-center justify-center gap-2 px-4 py-3.5 bg-primary text-primary-foreground rounded-xl font-semibold transition-all"
              >
                <motion.div
                  whileHover={{ scale: 1.1 }}
                  className="flex items-center justify-center gap-1"
                >
                  <Plus className="w-5 h-5" />
                  <span>New Chat</span>
                </motion.div>
              </motion.button>
            </div>

            {/* Conversations List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {conversations.length === 0 ? (
                <div className="text-center text-muted-foreground text-sm py-12">
                  No conversations yet
                </div>
              ) : (
                conversations.map((conversation) => (
                  <motion.div
                    key={conversation.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="group relative"
                  >
                    <button
                      onClick={() => onSelectConversation(conversation.id)}
                      className={`w-full flex items-start gap-3 px-3 py-3 rounded-xl transition-all text-left ${
                        currentConversationId === conversation.id
                          ? 'bg-sidebar-accent/80 text-sidebar-accent-foreground shadow-md'
                          : 'text-sidebar-foreground hover:bg-sidebar-accent/40'
                      }`}
                    >
                      <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        {renamingId === conversation.id ? (
                          <input
                            type="text"
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value)}
                            onBlur={() => handleRename(conversation.id, renameValue)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleRename(conversation.id, renameValue);
                              if (e.key === 'Escape') setRenamingId(null);
                            }}
                            onClick={(e) => e.stopPropagation()}
                            autoFocus
                            className="w-full text-sm font-medium bg-sidebar-accent px-2 py-1 rounded outline-none"
                          />
                        ) : (
                          <div className="text-sm font-medium truncate">
                            {conversation.title || 'New Conversation'}
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {Math.floor(conversation.messageCount / 2)} exchanges
                        </div>
                      </div>
                    </button>

                    {/* Menu Button */}
                    <div className="absolute right-2 top-2">
                      <motion.button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(openMenuId === conversation.id ? null : conversation.id);
                        }}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        className="p-1.5 bg-sidebar-accent/50 hover:bg-sidebar-accent rounded-md opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <MoreVertical className="w-3.5 h-3.5" />
                      </motion.button>

                      {/* Dropdown Menu */}
                      <AnimatePresence>
                        {openMenuId === conversation.id && (
                          <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: -10 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: -10 }}
                            transition={{ duration: 0.15 }}
                            className="absolute right-0 top-full mt-1 w-36 bg-card border border-border rounded-lg shadow-xl overflow-hidden z-50"
                          >
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setRenameValue(conversation.title || '');
                                setRenamingId(conversation.id);
                                setOpenMenuId(null);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-secondary transition-colors text-left"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                              Rename
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteConversation(conversation.id);
                                setOpenMenuId(null);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors text-left"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                              Delete
                            </button>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </motion.div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-sidebar-border">
              <div className="text-xs text-muted-foreground text-center">
                HeritageBot by Twinings
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
