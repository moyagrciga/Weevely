'''
Created on 28/ago/2011

@author: norby
'''

from core.module import Module, ModuleException
from random import choice
from string import letters
from core.http.request import Request
from urlparse import urlparse

classname = 'Webdir'
    
class Webdir(Module):
    '''Find writable first directory and get corresponding URL
    :find.webdir auto | <start dir>
    '''
    
    vectors = { 'shell.php' : { "fwrite()"       : "fwrite(fopen('%s','w'),'1');",
                           "file_put_contents"             : "file_put_contents('%s', '1');"
                            },
            'shell.sh' : {
                            "echo" : "echo '1' > %s"
                            }
           }
    
    def __init__( self, modhandler , url, password):

        self.dir = None
        self.url = None
        
        self.probe_filename = ''.join(choice(letters) for i in xrange(4)) + '.html'

        Module.__init__(self, modhandler, url, password)
        

    def __execute_payload(self, interpreter, vector, dir_path, file_path, file_url, dir_url):
        
        payload = self.vectors[interpreter][vector] % file_path
        self.modhandler.load(interpreter).run(payload)

        if self.modhandler.load('file.check').run(file_path, 'exists'):
                
            file_content = Request(file_url).read()
            if( file_content == '1'):
                self.dir = dir_path
                self.url = dir_url
                
            
            if self.modhandler.load('shell.php').run("unlink('%s') && print('1');" % file_path) != '1':
                print "[!] [find.webdir] Error cleaning test file %s" % (file_path)
                
            if self.dir and self.url:
                print "[find.webdir] Writable web dir: %s -> %s" % (self.dir, self.url)
                return True
                
            
        return False    
                
                        

    def run(self, start_dir):
        if self.url and self.dir:
            print "[find.webdir] Writable web dir: %s -> %s" % (self.dir, self.url)
            return
            
        if start_dir == 'auto':
            try:
                root_find_dir = self.modhandler.load('system.info').run('basedir')
            except ModuleException, e:
                print '[!] [' + e.module + '] ' + e.error
                root_find_dir = None
                
        else:
            root_find_dir = start_dir
        
        if root_find_dir:
            
            if not root_find_dir[-1]=='/': root_find_dir += '/'
            
            http_root = '%s://%s/' % (urlparse(self.url).scheme, urlparse(self.url).netloc) 
            
            try:
                writable_dirs = self.modhandler.load('find.perms').run('all', 'dir', 'w', root_find_dir).split('\n')
            except Exception as e:
                print '[!] [' + e.module + '] ' + e.error
                writable_dirs = []
                
               
            for dir_path in writable_dirs:
            
            
                if not dir_path[-1]=='/': dir_path += '/'
                file_path = dir_path + self.probe_filename
    
                file_url = http_root + file_path.replace(root_find_dir,'')
                dir_url = http_root + dir_path.replace(root_find_dir,'')
            
                interpreter, vector = self._get_default_vector()
                if interpreter and vector:
                    response = self.__execute_payload(interpreter, vector, dir_path, file_path, file_url, dir_url)
                    if response:
                        return response
                    
                for interpreter in self.vectors:
                    if interpreter in self.modhandler.loaded_shells:
                        for vector in self.vectors[interpreter]:
                            response = self.__execute_payload(interpreter, vector, dir_path, file_path, file_url, dir_url)
                            if response:
                                return response
                 
        if not (self.url and self.dir):
            raise ModuleException(self.name,  "Writable web directory not found")